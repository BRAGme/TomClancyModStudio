r"""Make a Tk callback fault fail a smoke test instead of only printing it.

Tk catches an exception raised inside a callback -- a button command, a
binding, an `after` job -- and hands it to `Tk.report_callback_exception`. The
default writes a traceback to stderr and carries on, so the run continues, the
test's own failure list never hears about it, and the last line still reports
success.

That combination is worse than having no test at all: it supplies the
reassurance without doing the checking. It is also not hypothetical. The
sister project's smoke test printed a traceback out of the GUI message pump on
every single run for most of a session and reported zero failures throughout,
because the counter and the traceback were independent -- and the repeated
lines had started being filtered away as noise by the person reading them.

Faults are still written to stderr, exactly as before. They are now also
collected and labelled with whatever was on screen at the time, so a fault
names the page that produced it rather than arriving as a bare stack.

Both smoke tests in this folder keep their failures in a different shape, so
the collected faults are handed back in either one.
"""

from __future__ import annotations

import sys
import traceback


class CallbackWatch:
    """Install on the root window, then read `faults` when the run ends."""

    def __init__(self, app, where="start-up"):
        self.faults = []
        self.where = where
        app.report_callback_exception = self._report

    def _report(self, exc, val, tb):
        text = "".join(traceback.format_exception(exc, val, tb))
        self.faults.append((self.where, val, text))
        sys.stderr.write(text)          # still shown, exactly as before

    def as_tuples(self):
        """`(label, exception, traceback)`, for a list of tuples."""
        return [("Tk callback: %s" % where, val, text)
                for where, val, text in self.faults]

    def as_strings(self):
        """One formatted block each, for a list of strings."""
        return ["Tk callback fault, %s\n%s" % (where, text)
                for where, _val, text in self.faults]
