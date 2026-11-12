"""Import this from a test module that reaches the stagers (they call `dotnet run -c Release --project ...`): it puts a
`dotnet` stand-in first on PATH for the test process, so each call runs the already built dll instead of re-checking the
build (FAL-558: ~1.2 s a call here, several on the CI runner, and the stager tests make dozens). The stand-in falls back to the
real dotnet for every other command, for a missing dll and for a dll older than any source under dotnet/. POSIX only."""
import os

SHIM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dotnet_shim")


def install():
    if os.name != "posix" or os.environ.get("FO4SF_NO_DOTNET_SHIM"):
        return
    paths = os.environ.get("PATH", "").split(os.pathsep)
    if SHIM not in paths:
        os.environ["PATH"] = os.pathsep.join([SHIM] + paths)


install()
