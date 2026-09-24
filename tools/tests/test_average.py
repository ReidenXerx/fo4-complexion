"""The player's default is the "most average" preset of the pool, measured on the BODIES the pool gives
(silhouette_gen.body_values): a state, the shaft or fo4-anatomy's build slider is never written into a body
(S-16, S-29, S-62), so it never pulls the average either. On the owner's install taking them out changed no
winner, so a regeneration cannot tell -- this synthetic pool can (wave 5, lens 3 L10)."""
import unittest

import support
import base_body
import silhouette_gen as sg

# One vertex each: Breasts moves vertex 0, Erection (a state no body holds) vertex 1, ten times as far.
TRI = {'Breasts': {0: (1.0, 0.0, 0.0)}, 'Erection': {1: (0.0, 10.0, 0.0)}}
MORPHS = set(TRI)
TARGETS = {'A': {'Breasts': 0.5, 'Erection': 1.0}, 'B': {'Breasts': 0.6}, 'C': {'Breasts': 0.4}}


def winner(measure):
    pool = [(n, measure(t)) for n, t in TARGETS.items()]
    return base_body.most_average(pool, TRI, pool)[0]


class Average(unittest.TestCase):
    def test_a_slider_no_body_holds_is_not_part_of_the_average(self):
        self.assertEqual(sg.body_values({'Breasts': 0.5, 'Erection': 1.0, 'Penis Width': 1.0, 'AnatomyOpening': 0.5,
                                         'NotOnThisBody': 0.3}, MORPHS | {'Penis Width', 'AnatomyOpening'}),
                         {'Breasts': 0.5})

    def test_it_decides_which_preset_is_the_default(self):
        # GP-4: the control first -- counted, the state makes B the average; left out, A is exactly the mean.
        self.assertEqual(winner(lambda t: {k: v for k, v in t.items() if k in MORPHS}), 'B')
        self.assertEqual(winner(lambda t: sg.body_values(t, MORPHS)), 'A')


if __name__ == '__main__':
    unittest.main()
