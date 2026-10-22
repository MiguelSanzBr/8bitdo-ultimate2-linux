"""Tk's file dialog (backups) restyled in the window's colours, hidden files left out."""
from ultimate2.gui import theme


def test_file_dialog_in_the_window_colours(shared_app):
    a = shared_app
    w = ".__tk_filedialog"
    seen = {}

    def look():
        icons = f"{w}.contents.icons"
        seen["bg"] = a.tk.eval(f"{icons}.cHull.canvas cget -background")
        seen["fill"] = a.tk.eval(f"set [info object namespace {icons}]::fill")
        seen["hidden"] = a.tk.eval(f"{w}.contents.f2.hidden cget -state")     # not winfo ismapped: racy before the map
        a.tk.eval(f"{w}.contents.f2.cancel invoke")
    a.after(300, look)
    assert not a.tk.call("tk_getSaveFile", "-parent", ".", "-filetypes", [["Backup", "*.bin"]])   # cancelled
    assert seen == {"bg": theme.TILE, "fill": theme.FG, "hidden": "normal"}
    assert a.tk.eval("set ::tk::dialog::file::showHiddenVar") == "0"
    locale = a.tk.eval("::msgcat::mclocale")
    a.tk.eval("::msgcat::mclocale pt_br")
    try:
        assert a.tk.eval('namespace eval ::tk {::msgcat::mc "Show &Hidden Directories"}') == "Mostrar pastas &ocultas"
    finally:
        a.tk.eval(f"::msgcat::mclocale {locale}")
