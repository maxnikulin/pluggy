"""
Call loop machinery
"""
import sys

from ._result import HookCallError, _Result, _raise_wrapfail


def _multicall(hook_impls, caller_kwargs, firstresult=False):
    """Execute a call into multiple python functions/methods and return the
    result(s).

    ``caller_kwargs`` comes from _HookCaller.__call__().
    """
    __tracebackhide__ = True
    results = []
    excinfo = None
    try:  # run impl and wrapper setup functions in a loop
        teardowns = []
        try:
            for hook_impl in reversed(hook_impls):
                try:
                    args = [caller_kwargs[argname] for argname in hook_impl.argnames]
                except KeyError:
                    for argname in hook_impl.argnames:
                        if argname not in caller_kwargs:
                            raise HookCallError(
                                "hook call must provide argument %r" % (argname,)
                            )

                if hook_impl.hookwrapper:
                    gen = hook_impl.function(*args)

                    try:
                        next(gen)  # first yield
                    except StopIteration:
                        _raise_wrapfail(gen, "did not yield")

                    teardowns.append(gen)
                else:
                    res = hook_impl.function(*args)
                    if res is not None:
                        results.append(res)
                        if firstresult:  # halt further impl calls
                            break
        except BaseException:
            excinfo = sys.exc_info()
    finally:
        if firstresult:  # first result hooks return a single value
            outcome = _Result(results[0] if results else None, excinfo)
        else:
            outcome = _Result(results, excinfo)

        # run all wrapper post-yield blocks
        for gen in reversed(teardowns):
            try:
                try:
                    gen.send(outcome)
                    _raise_wrapfail(gen, "has second yield")
                except StopIteration:
                    pass
                finally:
                    # Exception is risen only if generator
                    # suppresses GeneratorExit exception and yield
                    # so _raise_wrapfail above is necessary
                    gen.close()
            except BaseException:
                outcome._excinfo = sys.exc_info()

        return outcome.get_result()
