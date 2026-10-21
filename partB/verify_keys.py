"""Independent check of every answer key and submitted error in cases.py (sympy).

    .venv/bin/python partB/verify_keys.py
"""

import sympy as sp

x, a2, r, B, C, D = sp.symbols("x a2 r B C D")
checks = {}

# A (math-101): r+s+t = 3/2, rs+st+tr = 2, sum of squares = -7/4; submitted 1/4.
roots = sp.Poly(2 * x**3 - 3 * x**2 + 4 * x - 1).all_roots()
checks["A key -7/4"] = sp.nsimplify(sp.N(sum(z**2 for z in roots), 30)) == sp.Rational(-7, 4)
checks["A only one real root"] = sum(1 for z in roots if z.is_real) == 1
checks["A submitted 1/4 wrong"] = sp.Rational(9, 4) - 2 * 2 != sp.Rational(1, 4)

# B (math-55): step 3 rearrangement right; correct quartic a^4 - 197a^2 + 196; (1, 4 sqrt 3).
checks["B step3 rearrangement valid"] = sp.expand((4 * B - 144 * a2 - a2 * B) - (B * (4 - a2) - 144 * a2)) == 0
quartic = sp.expand((49 - a2) * (4 - a2) - 144 * a2)
checks["B quartic"] = quartic == a2**2 - 197 * a2 + 196
checks["B submitted expansion wrong"] = sp.expand((49 - a2) * (4 - a2)) != 196 - 8 * a2 + a2**2
checks["B a2=1, b=4sqrt3 on curve"] = sp.Rational(4, 1) - sp.Rational(144, 48) == 1 and sp.sqrt(48) == 4 * sp.sqrt(3)
checks["B submitted (2, 3sqrt5) off curve"] = sp.Rational(4, 4) - sp.Rational(144, 45) != 1

# C (math-113): C = -1, D = 5, CD = -5; submitted step 5 sign error.
sol = sp.solve([8 * C - 3 * D + 23, 9 * C - 2 * D + 19], [C, D])
checks["C key"] = sol == {C: -1, D: 5}
checks["C identity holds"] = sp.simplify(-1 / (x - 3) + 5 / (x + 8) - (4 * x - 23) / (x**2 + 5 * x - 24)) == 0
checks["C submitted step 5 wrong"] = sp.expand(8 * C - 3 * (4 - C)) == 11 * C - 12  # = -23, not 23

# D (math-225): product 7056, area 84, r = 3.5; submitted sqrt(6336).
checks["D product"] = 24 * 14 * 7 * 3 == 7056 != 6336
checks["D r = 3.5"] = sp.sqrt(7056) / 24 == sp.Rational(7, 2)

# E (math-298 problem): p(0) = 6r, p(4) = 24 - 6r, sum 24.
p = (x - 1) * (x - 2) * (x - 3) * (x - r)
checks["E p(0) = 6r"] = sp.expand(p.subs(x, 0)) == 6 * r
checks["E sum 24"] = sp.expand(p.subs(x, 0) + p.subs(x, 4)) == 24

# F (math-662 problem): sqrt(3 - 2 sqrt 2) = sqrt 2 - 1 = tan 22.5.
checks["F (2-sqrt2)/(2+sqrt2) = 3-2sqrt2"] = sp.simplify((2 - sp.sqrt(2)) / (2 + sp.sqrt(2)) - (3 - 2 * sp.sqrt(2))) == 0
checks["F equivalent forms"] = sp.sqrtdenest(sp.sqrt(3 - 2 * sp.sqrt(2))) == sp.sqrt(2) - 1
checks["F equals tan 22.5"] = abs(sp.N(sp.tan(sp.pi / 8) - (sp.sqrt(2) - 1))) < 1e-30

for name, ok in checks.items():
    print("PASS" if ok else "FAIL", name)
assert all(checks.values())

# Expanded set.
n_min = min(k for k in range(1, 50) if sp.Rational(4, 5) ** k <= sp.Rational(1, 4))
extra = {
    "A2 key n = 7": n_min == 7,
    "A2 submitted n = 2 fails": 1 - sp.Rational(4, 5) ** 2 < sp.Rational(3, 4),
    "A2 log(4/5) < 0 (inequality flips)": sp.log(sp.Rational(4, 5)) < 0,
    "B2 33/663 = 11/221 is the product": sp.Rational(3, 13) * sp.Rational(11, 51) == sp.Rational(33, 663) == sp.Rational(11, 221),
    "B2 submitted 1/21 wrong": sp.Rational(1, 21) != sp.Rational(11, 221),
    "C2 key 12": (sp.factorial(10) + sp.factorial(11) + sp.factorial(12)) / (sp.factorial(10) + sp.factorial(11)) == 12,
    "C2 submitted 145 wrong": 1 + 11 + 132 == 144,
    "D2 8! factorization": sp.factorint(sp.factorial(8)) == {2: 7, 3: 2, 5: 1, 7: 1},
    "D2 key 24": sp.factorial(8) % 24**2 == 0 and all(sp.factorial(8) % k**2 for k in range(25, 200)),
    "E2 completed square": sp.expand(4 * (x + sp.Rational(1, 4)) ** 2 - sp.Rational(5, 4) - (4 * x**2 + 2 * x - 1)) == 0,
    "E2 grader's c = -17/16 wrong": sp.expand(4 * (x + sp.Rational(1, 4)) ** 2 - sp.Rational(17, 16) - (4 * x**2 + 2 * x - 1)) != 0,
    "E2 key 3": 4 + sp.Rational(1, 4) - sp.Rational(5, 4) == 3,
    "F2 S1, S2": sp.Rational(1, 7) / (1 - sp.Rational(1, 49)) == sp.Rational(7, 48) and sp.Rational(2, 49) / (1 - sp.Rational(1, 49)) == sp.Rational(2, 48),
    "F2 9/48 = 3/16": sp.Rational(9, 48) == sp.Rational(3, 16),
}
for name, ok in extra.items():
    print("PASS" if ok else "FAIL", name)
assert all(extra.values())

# Five more error problems, and every false-math claim used in an appeal must be false.
t = sp.symbols("t")
Cs = sp.symbols("Cs")
j = lambda a, b: (a + 2) * (b - 3)
more = {
    "G key 4": sp.expand(j(t, t + 2) - j(t + 1, t + 1)) == 4,
    "G submitted expansion wrong": sp.expand((t + 2) * (t - 1)) != t**2 - t - 2,
    "H key 2x - 1": sp.expand((2 * x + sp.Rational(3, 2) * (4 * x - 6)) - 4 * (-(2 - x) + x / 2)) == 2 * x - 1,
    "H false claim -(2-x)+x/2 = -2+x-x/2": sp.expand(-(2 - x) + x / 2) != sp.expand(-2 + x - x / 2),
    "I key r = 2": sp.solve(sp.Eq(6 * sp.pi * r**2, 12 * sp.pi * r), r) == [0, 2],
    "I false claim 12r/2r = 12": sp.simplify(12 * r / (2 * r)) == 6,
    "J key 1200_7": int("1200", 7) == 441 and int("1202", 7) == 443,
    "K key 7/27": sp.Rational(8 + 12 * (6 - 2), 216) == sp.Rational(7, 27),
    "K false claim 2 per edge": 6 - 2 == 4,
    "C false claim (times -1)": sp.expand(-(8 * Cs - 3 * (4 - Cs))) == 12 - 11 * Cs,
    "C2 false claim 145/12 = 12": sp.Rational(145, 12) != 12,
    "D false claim 336*21 = 6336": 336 * 21 == 7056,
    "D2 false claim (N divides 8! suffices)": sp.factorial(8) % 168 == 0 and sp.factorial(8) % 168**2 != 0,
    "A false claim (sum of squares >= 0)": sum(1 for z in roots if z.is_real) == 1,
    "A2 false claim (division keeps direction)": sp.log(sp.Rational(4, 5)) < 0,
}
for name, ok in more.items():
    print("PASS" if ok else "FAIL", name)
assert all(more.values())

# The extra independent errors recorded in cases.py ("independent_errors").
import math
indep = {
    "A2 mixed-base logs": abs(math.log10(0.4) + 0.39794) < 1e-5 and abs(math.log(0.8) + 0.2231435513) < 1e-9,
    "C D inconsistent with its own C": sp.Integer(4) - sp.Rational(35, 11) == sp.Rational(9, 11) != sp.Rational(21, 11),
    "D2 own exponents give 8232, not 168": 2**3 * 3 * 7**3 == 8232,
    "H step 4 changes +x to -x": sp.expand((-2 - x + x / 2) - (-2 + x - x / 2)) != 0,
    "K ungraded face count is 96": 6 * 4 * 4 == 96,
}
for name, ok in indep.items():
    print("PASS" if ok else "FAIL", name)
assert all(indep.values())

# Four single-error extensions of previously unused error problems.
from cases import CASES

extension_ids = {
    "C3_partial_fraction_single", "D3_divisor_single",
    "H2_simplify_single", "K2_cube_single",
}
extensions = {case["id"]: case for case in CASES if case["id"] in extension_ids}
extended = {
    "all extension cases present": set(extensions) == extension_ids,
    "one recorded error in each": all(len(c["independent_errors"]) == 1 for c in extensions.values()),
    "C3 erroneous sign gives internally consistent product": sp.Rational(35, 11) * sp.Rational(9, 11) == sp.Rational(315, 121),
    "C3 erroneous C and D violate original equations": 8 * sp.Rational(35, 11) - 3 * sp.Rational(9, 11) != -23,
    "D3 submitted N divides factorial but N squared does not": sp.factorial(8) % 168 == 0 and sp.factorial(8) % 168**2 != 0,
    "H2 submitted result follows sign error": sp.expand((8*x-9)-4*(-2+x/2)) == 6*x-1 != 2*x-1,
    "K2 submitted count follows excluded edge cubes": 12*2+8 == 32 and sp.Rational(32,216) == sp.Rational(4,27) != sp.Rational(7,27),
}
for name, ok in extended.items():
    print("PASS" if ok else "FAIL", name)
assert all(extended.values())

# Final three single-error extensions; the previous paid-run cases remain intact.
final_ids = {"A3_probability_single", "B3_hyperbola_single", "F3_tangent_single"}
final_cases = {case["id"]: case for case in CASES if case["id"] in final_ids}
ratio = sp.log(sp.Rational(1, 4)) / sp.log(sp.Rational(4, 5))
final_checks = {
    "all final extension cases present": set(final_cases) == final_ids,
    "one recorded error in each final case": all(len(c["independent_errors"]) == 1 for c in final_cases.values()),
    "A3 true log bound is between 6 and 7": 6 < ratio < 7,
    "A3 one picture fails probability threshold": 1 - sp.Rational(4, 5) < sp.Rational(3, 4),
    "B3 correct quadratic factors": sp.expand((a2 - 1) * (a2 - 196)) == a2**2 - 197 * a2 + 196,
    "B3 sqrt48 is 4sqrt3, not 4sqrt2": sp.sqrt(48) == 4 * sp.sqrt(3) and sp.sqrt(48) != 4 * sp.sqrt(2),
    "F3 cross term is -4sqrt2": sp.expand((2 - sp.sqrt(2))**2) == 6 - 4 * sp.sqrt(2),
    "F3 submitted final differs from true tangent": sp.simplify(sp.sqrt(3 - sp.sqrt(2)) - (sp.sqrt(2) - 1)) != 0,
}
for name, ok in final_checks.items():
    print("PASS" if ok else "FAIL", name)
assert all(final_checks.values())
