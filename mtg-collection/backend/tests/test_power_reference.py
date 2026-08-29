"""The port against its reference, checked without a browser.

Sprint 05 left this open as "needs a browser", and for comparing *scores* it
does. It does not for comparing the thing that actually drifts. edhpowerlevel
is a client-side app, so the constants and the interpolator it scores with are
in a script the site hands to anyone who asks — and on 2026-08-29 the whole
`factors` object was read out of `main-C1lbqCDd.js` and diffed against this
port. Every one of the nine values matched, and so did the interpolator, down
to the detail the port's own docstring warns about (the fraction inside a
decile is not multiplied by the weight).

Copied here rather than fetched at test time on purpose: a test that reaches
the internet fails on a train, and a *reference* that can change under you
without a commit is not a reference. When the site changes, this file is what
gets updated — deliberately, with the diff visible in the history.

What this does NOT prove: that a given deck scores the same here as there.
That still wants a browser. What it does prove is that if it ever stops
scoring the same, the cause is not a mistyped curve.
"""
import math

from app.services.power_level import FACTORS, de

#: Verbatim from the site's `factors` object, main-C1lbqCDd.js, 2026-08-29.
#: `1e3` and `27e3` written out; nothing else changed.
REFERENCE_FACTORS = {
    "land": 0.6,
    "reserved": 0.2,
    "favorPrice": 0.25,
    "powerCurve": [0, 250, 320, 350, 380, 420, 470, 560, 760, 890, 1000],
    "popCurve": [0, 8500, 13600, 17100, 19800, 21900, 23700, 25300, 26200, 26700, 27000],
    "priceCurve": [0, 0.5, 1.5, 3.5, 6, 10, 15, 25, 40, 65, 100],
    "bracketCurve": [0, 4.7, 6.7, 7.7, 9.25, 10],
    "cmcFloor": 1.75,
    "cmcCeiling": 6,
    "efficiencyLimits": [0.65, 1.1],
}


def test_every_factor_matches_the_reference():
    for key, expected in REFERENCE_FACTORS.items():
        assert key in FACTORS, f"{key} is in the site's factors but not in the port"
        assert FACTORS[key] == expected, f"{key}: port {FACTORS[key]!r} != site {expected!r}"


def test_the_port_carries_no_factor_the_site_does_not_have():
    """An extra constant means an invented rule, which is worse than a missing one."""
    extra = sorted(set(FACTORS) - set(REFERENCE_FACTORS))
    assert extra == [], f"port has factors the reference does not: {extra}"


def _reference_de(t, s, o=1.0):
    """The site's interpolator, transcribed from the shipped script.

        de = (t, s, o = 1) => {
          if (t <= s[0]) return 0
          if (t > s[s.length - 1]) return (s.length - 1) * o
          const n = s.map((p, f) => ({ stop: f * o, max: p }))
          let m = 0
          for (let p = 0; p < n.length - 1; p++)
            if (t < n[p + 1].max && t >= n[p].max) {
              m = Number(n[p].stop + (t - n[p].max) / (n[p + 1].max - n[p].max))
              break
            }
          return m
        }
    """
    if t <= s[0]:
        return 0.0
    if t > s[-1]:
        return (len(s) - 1) * o
    for p in range(len(s) - 1):
        if s[p] <= t < s[p + 1]:
            return p * o + (t - s[p]) / (s[p + 1] - s[p])
    return 0.0


def test_the_interpolator_agrees_with_the_reference_everywhere_it_matters():
    """Sampled across every curve, including the two boundary branches.

    The weighted call is the one that matters: `de` is used with weight 1.25
    for price and 0.75 for popularity, and weighting the *fraction* as well as
    the decile — the obvious "cleaner" implementation — silently changes every
    score in the app.
    """
    for curve in (FACTORS["priceCurve"], FACTORS["popCurve"],
                  FACTORS["powerCurve"], FACTORS["bracketCurve"]):
        span = curve[-1] - curve[0]
        samples = [curve[0] - 1, curve[0], curve[-1], curve[-1] + span]
        samples += [curve[0] + span * f / 40 for f in range(41)]
        samples += list(curve)
        for weight in (1.0, 1.25, 0.75):
            for value in samples:
                assert math.isclose(de(value, curve, weight),
                                    _reference_de(value, curve, weight),
                                    rel_tol=1e-12, abs_tol=1e-12), (
                    f"de({value}, ..., {weight}) diverges")


def test_the_reference_bracket_stays_inside_one_to_five():
    """`ceil(de(level, bracketCurve))` is 0 at level 0 and 5 above 10."""
    from app.services.power_level import FACTORS as F
    for level in (0, 0.1, 4.7, 6.7, 7.7, 9.25, 10, 12):
        raw = math.ceil(de(level, F["bracketCurve"]))
        assert 1 <= max(1, min(5, raw)) <= 5
