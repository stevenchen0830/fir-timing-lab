#!/usr/bin/env python3
"""Deterministic non-clock buffer trees, with exact identity-contraction checks.

Technology-specific cells/models remain external. This is an electrical
conditioning experiment, not CTS, a floorplan, or extracted timing closure.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math


def fingerprint(module, collapse=lambda b: b, ignore=frozenset()):
    h = hashlib.sha256()
    for name in sorted(module['ports']):
        port = dict(module['ports'][name])
        port['bits'] = [collapse(b) for b in port['bits']]
        h.update(json.dumps(['port', name, port], sort_keys=True).encode())
    for name in sorted(module['cells']):
        if name in ignore:
            continue
        cell = dict(module['cells'][name])
        cell['connections'] = {p: [collapse(b) for b in bits] for p, bits in cell['connections'].items()}
        h.update(json.dumps(['cell', name, cell], sort_keys=True).encode())
    return h.hexdigest()


def sink_counts(module):
    counts = Counter()
    for cell in module['cells'].values():
        for port, bits in cell['connections'].items():
            direction = cell['port_directions'][port]
            if direction == 'inout':
                raise ValueError('Tri-state/inout cell requires a separate ECO policy')
            if direction == 'input':
                counts.update(b for b in bits if isinstance(b, int))
    for port in module['ports'].values():
        if port['direction'] == 'inout':
            raise ValueError('Top-level inout not supported')
        if port['direction'] == 'output':
            counts.update(b for b in port['bits'] if isinstance(b, int))
    return counts


def buffer_module(module, limit=16, buffer_type='BUFX8', input_pin='A', output_pin='Y'):
    if limit < 2:
        raise ValueError('Fanout limit must be at least two')
    if any(n.startswith('__FO_') for n in [*module['netnames'], *module['cells']]):
        raise ValueError('Buffer namespace already exists; use the unmodified candidate')
    before = fingerprint(module)
    original_cells = len(module['cells'])
    clock_bits = set(module['ports']['clk']['bits'])
    counts = sink_counts(module)
    selected = {b for b, n in counts.items() if n > limit and b not in clock_bits}
    sinks = defaultdict(list)
    for name in sorted(module['cells']):
        cell = module['cells'][name]
        for port in sorted(cell['connections']):
            if cell['port_directions'][port] == 'input':
                for index, bit in enumerate(cell['connections'][port]):
                    if bit in selected:
                        sinks[bit].append(('cell', name, port, index))
    for name in sorted(module['ports']):
        port = module['ports'][name]
        if port['direction'] == 'output':
            for index, bit in enumerate(port['bits']):
                if bit in selected:
                    sinks[bit].append(('port', name, '', index))
    all_bits = [b for net in module['netnames'].values() for b in net['bits'] if isinstance(b, int)]
    next_bit = max(all_bits, default=1) + 1
    added, inverse = set(), {}

    def make_buffer(source):
        nonlocal next_bit
        bit = next_bit
        next_bit += 1
        name = f'__FO_BUF_{len(added):06d}'
        net = f'__FO_NET_{len(added):06d}'
        module['cells'][name] = {'hide_name': 0, 'type': buffer_type, 'parameters': {},
            'attributes': {}, 'port_directions': {input_pin: 'input', output_pin: 'output'},
            'connections': {input_pin: [source], output_pin: [bit]}}
        module['netnames'][net] = {'hide_name': 0, 'bits': [bit], 'attributes': {}}
        added.add(name)
        inverse[bit] = source
        return bit

    def connect(ref, bit):
        kind, name, port, index = ref
        if kind == 'cell':
            module['cells'][name]['connections'][port][index] = bit
        else:
            module['ports'][name]['bits'][index] = bit
            module['netnames'][name]['bits'][index] = bit

    def distribute(source, refs):
        if len(refs) <= limit:
            for ref in refs:
                connect(ref, source)
        else:
            size = math.ceil(len(refs) / limit)
            for start in range(0, len(refs), size):
                distribute(make_buffer(source), refs[start:start + size])

    for bit in sorted(selected):
        # One root buffer isolates the original weak driver from tree fanout.
        distribute(make_buffer(bit), sinks[bit])

    def collapse(bit):
        seen = set()
        while bit in inverse:
            if bit in seen:
                raise ValueError('Cycle in inserted buffer tree')
            seen.add(bit)
            bit = inverse[bit]
        return bit

    if fingerprint(module, collapse, added) != before:
        raise ValueError('Identity contraction does not recover original circuit')
    after = sink_counts(module)
    if any(n > limit for b, n in after.items() if b not in clock_bits):
        raise ValueError('Non-clock fanout cap was not achieved')
    return {'status': 'BUFFER_IDENTITY_CONTRACTION_PASS', 'original_cells': original_cells,
        'added_buffers': len(added), 'buffer_cell': buffer_type, 'fanout_limit': limit,
        'affected_original_nets': len(selected), 'clock_untouched': True,
        'original_max_nonclock_fanout': max((n for b, n in counts.items() if b not in clock_bits), default=0),
        'final_max_nonclock_fanout': max((n for b, n in after.items() if b not in clock_bits), default=0),
        'electrical_connectivity_fingerprint': before,
        'proof_scope': 'bitwise identity after contracting verified A-to-Y buffers; not timing/SDF/full RTL LEC'}
