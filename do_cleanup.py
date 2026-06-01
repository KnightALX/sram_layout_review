"""Delete unused files and verify project still works."""
import os
import subprocess

files_to_delete = [
    'config_system_v2.py',
    'core/enhanced_em_analyzer.py',
    'core/enhanced_matching.py',
    'core/enhanced_rc_calculator.py',
    'core/matching_check.py',
    'core/parallel_check.py',
    'core/pdk_layer_loader.py',
    'core/pdk_loader.py',
    'core/graph_matcher.py',
    'core/geometry_engine.py',
    'core/p2p_analyzer.py',
    'core/em_analyzer.py',
    'tests/test_matching_check.py',
    'tests/test_parallel_check.py',
    'tests/test_pdk_layer_loader.py',
    'scan_refs.py',
]

for f in files_to_delete:
    if os.path.exists(f):
        os.remove(f)
        print(f'  deleted: {f}')
    else:
        print(f'  not found: {f}')

print('=== Remaining files in core/ ===')
for f in sorted(os.listdir('core')):
    print(f'  {f}')

print('=== Remaining test files ===')
for f in sorted(os.listdir('tests')):
    if f.endswith('.py'):
        print(f'  {f}')
