"""Small regressions for the LaTeX/mathtext label adapter."""

from src import plotstyle


def test_tex_keeps_percent_and_ampersand_escapes():
    plotstyle.use(usetex=False)
    assert plotstyle.tex(r"Gross ($-0.48\%$ p.a.)") == r"Gross ($-0.48\%$ p.a.)"
    assert plotstyle.tex(r"A \& B") == r"A \& B"


def test_tex_removes_spacing_escapes_without_usetex():
    plotstyle.use(usetex=False)
    assert plotstyle.tex(r"A\,B\;C") == "A B C"
    assert plotstyle.tex(r"included\ impact") == "included impact"
