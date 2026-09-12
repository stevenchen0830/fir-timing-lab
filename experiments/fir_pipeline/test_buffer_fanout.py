import json
import unittest
from buffer_fanout import buffer_module, sink_counts


def toy():
    m = {'ports': {'clk': {'direction': 'input', 'bits': [2]},
                   'en': {'direction': 'input', 'bits': [3]},
                   'q': {'direction': 'output', 'bits': [3] * 7}},
         'cells': {}, 'netnames': {'clk': {'bits': [2]}, 'en': {'bits': [3]}, 'q': {'bits': [3] * 7}}}
    for i in range(41):
        m['cells'][f'ff{i}'] = {'type': 'EDFF', 'port_directions': {'CK': 'input', 'E': 'input', 'Q': 'output'},
            'connections': {'CK': [2], 'E': [3], 'Q': [4 + i]}}
        m['netnames'][f'n{i}'] = {'bits': [4 + i]}
    return json.loads(json.dumps(m))


class BufferTest(unittest.TestCase):
    def test_high_fanout_and_outputs(self):
        m = toy()
        report = buffer_module(m, limit=4)
        self.assertEqual(report['status'], 'BUFFER_IDENTITY_CONTRACTION_PASS')
        self.assertEqual(report['original_max_nonclock_fanout'], 48)
        self.assertLessEqual(report['final_max_nonclock_fanout'], 4)
        self.assertEqual(sink_counts(m)[2], 41)
        self.assertEqual(m['ports']['q']['bits'], m['netnames']['q']['bits'])

    def test_deterministic(self):
        a, b = toy(), toy()
        self.assertEqual(buffer_module(a), buffer_module(b))
        self.assertEqual(a, b)

    def test_noop_and_reject_reapplication(self):
        m = toy()
        self.assertEqual(buffer_module(m, 100)['added_buffers'], 0)
        buffer_module(m)
        with self.assertRaises(ValueError):
            buffer_module(m)


if __name__ == '__main__':
    unittest.main()
