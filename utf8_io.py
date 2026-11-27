"""Force UTF-8 text IO, imported FIRST by every entry script.

Windows Python defaults text files to cp1252, which cannot encode emoji (e.g. U+1F525
in captions) or accented product titles, so write_text/open crash there. CI (Linux) is
already UTF-8 and never hit it. Importing this module makes open(), Path.read_text and
Path.write_text default to UTF-8 everywhere, independent of the shell or PYTHONUTF8.
"""
import builtins
import pathlib

if not getattr(builtins, "_utf8_io_patched", False):
    _open = builtins.open

    def open(file, mode="r", *args, **kwargs):  # noqa: A001 - intentional shadow of builtins.open
        if "b" not in mode and kwargs.get("encoding") is None:
            kwargs["encoding"] = "utf-8"
        return _open(file, mode, *args, **kwargs)

    builtins.open = open

    _write_text = pathlib.Path.write_text

    def write_text(self, data, encoding=None, errors=None, newline=None):
        return _write_text(self, data, encoding=encoding or "utf-8", errors=errors, newline=newline)

    pathlib.Path.write_text = write_text

    _read_text = pathlib.Path.read_text

    def read_text(self, encoding=None, errors=None):
        return _read_text(self, encoding=encoding or "utf-8", errors=errors)

    pathlib.Path.read_text = read_text

    builtins._utf8_io_patched = True
