"""silhouette_gen.judge_base: a measured base whose baked values are ALL never part of a body -- fo4-anatomy's
build slider at its set default, the shaft, a state -- is zeroed for Silhouette, and what the build baked in
stays visible as 'owned' (S-62). Synthetic measurements: no game Data needed."""
import copy
import unittest

import support  # noqa: F401  (puts the tools under test on the path)
import silhouette_gen as sg


def measured(status='preset', baked=None, **more):
    """What base_body.measure returns, reduced to what judge_base reads."""
    return {'status': status, 'baked': baked, 'set': {'name': 'CBBE Body'}, 'preset': 'Anatomy Default',
            'note': 'measured', 'unexplained': 0.0, **more}


class JudgeBase(unittest.TestCase):
    def test_only_the_anatomy_build_slider_baked_in_is_zeroed(self):
        b = sg.judge_base(measured(baked={'AnatomyOpening': 0.5}))
        self.assertEqual(b['status'], 'zeroed')
        self.assertEqual(b['baked'], {})
        self.assertEqual(b['owned'], {'AnatomyOpening': 0.5})

    def test_the_shaft_and_a_state_baked_in_are_zeroed_too(self):
        b = sg.judge_base(measured(baked={'Penis Length': 0.3, 'Erection': 1.0, 'AnatomyOpening': 0.2}))
        self.assertEqual(b['status'], 'zeroed')
        self.assertEqual(b['owned'], {'Penis Length': 0.3, 'Erection': 1.0, 'AnatomyOpening': 0.2})

    def test_in_any_case(self):
        b = sg.judge_base(measured(baked={'anatomyopening': 0.5, 'PENIS WIDTH': 0.1}))
        self.assertEqual(b['status'], 'zeroed')

    def test_a_body_slider_baked_in_keeps_it_a_preset(self):
        b = sg.judge_base(measured(baked={'AnatomyOpening': 0.5, 'Breasts': 0.2}))
        self.assertEqual(b['status'], 'preset')
        self.assertEqual(b['baked'], {'AnatomyOpening': 0.5, 'Breasts': 0.2})
        self.assertEqual(b['owned'], {'AnatomyOpening': 0.5})

    def test_a_value_below_what_a_file_can_say_is_not_baked(self):
        # 5e-5 is below the last digit the files write: it neither makes a base a preset nor counts as owned.
        b = sg.judge_base(measured(baked={'AnatomyOpening': 0.5, 'Breasts': 0.00004}))
        self.assertEqual(b['status'], 'zeroed')
        self.assertEqual(b['owned'], {'AnatomyOpening': 0.5})

    def test_a_base_measured_zeroed_or_unknown_is_left_as_it_is(self):
        for m in (measured(status='zeroed', baked={}), measured(status='unknown', baked=None),
                  measured(status='preset', baked={}), measured(status='preset', baked=None)):
            with self.subTest(status=m['status'], baked=m['baked']):
                b = sg.judge_base(m)
                self.assertEqual({k: v for k, v in b.items() if k != 'owned'}, m)
                self.assertEqual(b['owned'], {})

    def test_the_measurement_itself_is_not_changed(self):
        m = measured(baked={'AnatomyOpening': 0.5})
        before = copy.deepcopy(m)
        sg.judge_base(m)
        self.assertEqual(m, before)

    def test_describe_says_what_the_build_owns(self):
        text = sg.describe(sg.judge_base(measured(baked={'AnatomyOpening': 0.5})))
        self.assertIn('AnatomyOpening', text)


if __name__ == '__main__':
    unittest.main()
