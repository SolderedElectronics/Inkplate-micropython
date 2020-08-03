import pytest
from bdf_font import Font, BDFFont


def test_add_empty():
    f = Font()
    f[33] = "!"
    assert f[33] == "!"
    assert f.start == 33
    assert len(f.ascii) == 1


def test_append_1():
    f = Font()
    f[33] = "!"
    f[34] = "@"
    assert f[33] == "!"
    assert f[34] == "@"
    assert f.start == 33
    assert len(f.ascii) == 2


def test_append_gap():
    f = Font()
    f[33] = "!"
    f[40] = "@"
    assert f[33] == "!"
    assert f[40] == "@"
    assert f.start == 33
    assert len(f.ascii) == 40 - 33 + 1


def test_prepend_1():
    f = Font()
    f[33] = "!"
    f[32] = "@"
    assert f[33] == "!"
    assert f[32] == "@"
    assert f.start == 32
    assert len(f.ascii) == 2


def test_prepend_gap():
    f = Font()
    f[33] = "!"
    f[20] = "@"
    assert f[33] == "!"
    assert f[20] == "@"
    assert f.start == 20
    assert len(f.ascii) == 33 - 20 + 1


def test_unicode():
    f = Font()
    f[33] = "!"
    f[200] = "@"
    assert f[33] == "!"
    assert f[200] == "@"
    assert f.start == 33
    assert len(f.ascii) == 1
    assert len(f.unicode) == 1


def test_get():
    f = Font()
    assert f[20] == None
    f[33] = "!"
    f[40] = "@"
    assert f[33] == "!"
    assert f[40] == "@"
    assert f[20] == None
    assert f[-2] == None
    assert f[35] == None
    assert f[50] == None
    assert f[500] == None

def test_contains():
    f = Font()
    assert not 20 in f
    f[33] = "!"
    f[40] = "@"
    assert 33 in f
    assert 40 in f
    assert not 20 in f
    assert not -2 in f
    assert not 35 in f
    assert not 50 in f
    assert not 500 in f

def test_load_font_1():
    f = BDFFont("luRS24.bdf")
    f.load_glyphs("Hello World!")
    for i in [ ord(c) for c in "Hello World!" ]:
        assert i in f
    h = f[ord("H")]
    print([i for i in f[ord("H")]])
    assert h[1] > h[0]
    assert h[2] > 0
    assert h[3] == 0
    assert h[4] >= h[0]
    assert h[5] == 0
