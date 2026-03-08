import json

with open(r'C:\Users\sksai\vip_signals.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

groups = {}
for item in data:
    g = item['group']
    if g not in groups:
        groups[g] = []
    if len(groups[g]) < 2:
        groups[g].append(item['text'])

with open('group_samples.txt', 'w', encoding='utf-8') as f:
    for g, samples in groups.items():
        f.write(f"=== {g} ===\n")
        for s in samples:
            f.write(f"{s}\n---\n")
