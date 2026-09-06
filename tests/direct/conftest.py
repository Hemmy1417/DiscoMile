"""Direct-mode harness for contracts/discovery_milestone.py.

The real contract module runs against a stub `genlayer` package that mirrors
the GenVM v0.6 SDK the contract targets (`import genlayer as gl`,
`gl.contract.Contract`, `gl.storage.allow`, `gl.vm.run_nondet`, UserError
carrying its text in `.data`, `gl.message.raw["datetime"]`, the EVM proxy's
`emit_transfer(value)` with no `on=`), and is AS STRICT AS the runtime where
it matters: DynArray refuses user construction, the validator function
actually runs, a validator returning False (or raising) surfaces as a failed
round rather than a settled state, and every transfer the contract emits is
recorded so a test can assert exactly what money moved.

The official genlayer-test direct runner cannot load this runner's SDK (its
GenVM archive is v0.3.0-rc7), so a stub is the honest harness here - the
semantic gate for this runner is the deployment itself, byte-verified in
docs/DEPLOYMENT.md.

Two external dependencies are mocked, narrowly (see tests/direct/support.py):

  THE WEB. `gl.nondet.web.get(url)` serves exact URLs from a table the test
  fills with bytes and a status; a URL not in the table is unreachable
  (raises), a URL marked 404 is NOT_FOUND. Every fetch is logged. Datasets
  are served as bytes and parsed by the contract exactly as on-chain.

  THE MODEL. `gl.nondet.exec_prompt` walks a queue of answers (the last
  entry repeats), so a test can hand the leader and a validator different
  answers and prove the comparison logic notices. Every prompt is logged.
"""

import importlib.util
import pathlib
import sys
import types

import pytest

CONTRACT_PATH = pathlib.Path(__file__).resolve().parents[2] / "contracts" / "discovery_milestone.py"

SPONSOR = "0x1111111111111111111111111111111111111111"
RESEARCHER = "0x2222222222222222222222222222222222222222"
STRANGER = "0x5555555555555555555555555555555555555555"

# Test transaction clock: an ISO instant the tests advance to pass time.
_CLOCK = ["2026-09-06T12:00:00Z"]
_PAGES = {}         # url -> (status:int, body:bytes)
_DEAD = set()       # url fragments that raise on fetch
_FETCHES = []
_PANEL = []
_PANEL_CALLS = [0]
_SENT = []
_PROMPTS = []


class _UserError(Exception):
    """v0.6 shape: the text lives in .data; str() returns it so that
    pytest.raises(match=...) reads the message."""
    def __init__(self, data):
        super().__init__(data)
        self.data = data

    def __str__(self):
        return str(self.data)


class _VMError:
    def __init__(self, message):
        self.message = message


class _Return:
    def __init__(self, calldata):
        self.calldata = calldata


def _run_nondet(leader_fn, validator_fn):
    """gl.vm.run_nondet: the leader runs; the validator sees Return(value)
    or the leader's UserError instance and answers a bool. False (or an
    escaping exception) is a disagreement - the round fails and nothing is
    written. A leader failure the validator endorses propagates as that
    same error."""
    try:
        value = leader_fn()
    except _UserError as e:
        try:
            agreed = validator_fn(e)
        except Exception:
            agreed = False
        if agreed:
            raise _UserError(e.data)
        raise _UserError("[LLM_ERROR] validators disagreed with the leader's failure")
    except Exception as e:
        try:
            agreed = validator_fn(_VMError(str(e)))
        except Exception:
            agreed = False
        if agreed:
            raise _UserError(str(e))
        raise _UserError("[LLM_ERROR] validators disagreed with the leader's failure")
    try:
        ok = validator_fn(_Return(value))
    except Exception:
        ok = False
    if not ok:
        raise _UserError("[LLM_ERROR] validators did not agree with the leader")
    return value


class _TreeMap(dict):
    def get(self, k, default=None):
        return super().get(k, default)

    def __class_getitem__(cls, item):
        return cls


class _U256(int):
    def __new__(cls, v):
        return super().__new__(cls, int(v))


class _DynArrayMeta(type):
    def __getitem__(cls, item):
        return cls


class _DynArray(list, metaclass=_DynArrayMeta):
    """Refuses user construction exactly like the runtime."""

    def __init__(self, *args, **kwargs):
        raise TypeError("this class can't be instantiated by user")

    @classmethod
    def _from_storage(cls, items=()):
        obj = list.__new__(cls)
        list.__init__(obj, items)
        return obj


class _Address(str):
    def __new__(cls, v):
        return super().__new__(cls, str(v))

    @property
    def as_hex(self):
        return str(self)


class _ViewDeco:
    def __call__(self, fn):
        return fn


class _WriteDeco:
    payable = staticmethod(lambda fn: fn)

    def __call__(self, fn):
        return fn


class _Public:
    view = _ViewDeco()
    write = _WriteDeco()


class _EvmProxyInstance:
    """The v0.6 runner's EVM proxy: emit_transfer(value) and nothing else -
    an `on=` keyword is a TypeError on-chain, so it is one here too."""
    def __init__(self, addr):
        self._addr = addr

    def emit_transfer(self, value):
        _SENT.append((str(self._addr).lower(), int(value)))


def _contract_interface(cls):
    return lambda addr: _EvmProxyInstance(addr)


class _Response:
    def __init__(self, status, body):
        self.status = status
        self.headers = {}
        self.body = body


class _NondetWeb:
    @staticmethod
    def post(url, body=None, headers=None):
        raise AssertionError(f"unexpected POST: {url}")

    @staticmethod
    def render(url, mode="text"):
        raise AssertionError(f"unexpected render: {url}")

    @staticmethod
    def get(url, **kw):
        _FETCHES.append(url)
        for fragment in _DEAD:
            if fragment in url:
                raise RuntimeError("source unreachable")
        if url in _PAGES:
            status, body = _PAGES[url]
            return _Response(status, body)
        raise RuntimeError("source unreachable")


def _exec_prompt(prompt, response_format=None):
    _PROMPTS.append(prompt)
    if not _PANEL:
        raise AssertionError("test ran the panel without panel_says()")
    idx = min(_PANEL_CALLS[0], len(_PANEL) - 1)
    _PANEL_CALLS[0] += 1
    answer = _PANEL[idx]
    if isinstance(answer, BaseException):
        raise answer
    return answer


class _Message(types.SimpleNamespace):
    """gl.message: sender_address / value attributes plus the raw dict with
    the transaction datetime, exactly as the v0.6 SDK exposes them."""
    @property
    def raw(self):
        return {"sender_address": self.sender_address, "value": self.value,
                "datetime": _CLOCK[0]}

    @property
    def datetime(self):
        return _CLOCK[0]


def _install():
    """Build the `genlayer` package the contract imports: `import genlayer as
    gl` plus `from genlayer.types import *`."""
    gl = types.ModuleType("genlayer")
    gl.IS_IN_VM = False
    gl.public = _Public()
    gl.contract = types.SimpleNamespace(Contract=type("Contract", (), {}))
    gl.storage = types.SimpleNamespace(allow=lambda cls: cls, TreeMap=_TreeMap,
                                       DynArray=_DynArray)
    gl.vm = types.SimpleNamespace(UserError=_UserError, VMError=_VMError,
                                  Return=_Return, run_nondet=_run_nondet)
    gl.nondet = types.SimpleNamespace(web=_NondetWeb(), exec_prompt=_exec_prompt)
    gl.evm = types.SimpleNamespace(contract_interface=_contract_interface)
    gl.message = _Message(sender_address=SPONSOR, value=0)

    gl_types = types.ModuleType("genlayer.types")
    gl_types.u256 = _U256
    gl_types.Address = _Address
    gl_types.__all__ = ["u256", "Address"]
    gl.types = gl_types

    sys.modules["genlayer"] = gl
    sys.modules["genlayer.types"] = gl_types
    return gl


def _load():
    _install()
    spec = importlib.util.spec_from_file_location("discovery_milestone_contract", CONTRACT_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def module():
    return _load()


@pytest.fixture
def c(module):
    """A fresh contract instance with zeroed storage and reset mocks."""
    _CLOCK[0] = "2026-09-06T12:00:00Z"
    _PAGES.clear()
    _DEAD.clear()
    _FETCHES.clear()
    _SENT.clear()
    _PROMPTS.clear()
    _PANEL.clear()
    _PANEL_CALLS[0] = 0
    module.gl.message.sender_address = SPONSOR
    module.gl.message.value = 0
    inst = module.DiscoveryMilestone()
    for name in ("agreements", "sources_store", "requirements_store", "packages_store",
                 "receipts_store", "sponsor_index", "researcher_index", "claimable"):
        setattr(inst, name, module.gl.storage.TreeMap())
    inst.agreement_ids = _DynArray._from_storage()
    inst.total_agreements = module.u256(0)
    inst.escrow_total_atto = module.u256(0)
    inst.ledger_total_atto = module.u256(0)
    return inst


# The mock surface the support module and the tests drive.
STATE = types.SimpleNamespace(clock=_CLOCK, pages=_PAGES, dead=_DEAD,
                              fetches=_FETCHES, panel=_PANEL,
                              panel_calls=_PANEL_CALLS, sent=_SENT,
                              prompts=_PROMPTS, Return=_Return,
                              UserError=_UserError, VMError=_VMError)
