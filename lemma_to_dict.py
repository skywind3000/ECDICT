import json

result_dict = {}
conflicts = []

with open("lemma.en.txt", "r") as infile:
    for line in infile:
        if line.startswith(";"):
            # ignore comments
            continue

        split_line = line.strip().split("->")
        key_words = split_line[1].split(",")
        value = split_line[0].split("/")[0].strip()

        if result_dict.get(value):
            dup = f"{value}:{result_dict.get(value)} -> {value}:{value}"
            print(f"{dup} exists")
            conflicts.append(dup)
        else:
            result_dict[value] = value

        for keyword in key_words:
            kw = keyword.strip()
            if result_dict.get(kw):
                dup = f"{kw}:{result_dict.get(kw)} -> {kw}:{value}"
                print(f"{dup} exists")
                conflicts.append(dup)
                continue
            result_dict[kw] = value

print(f"{len(result_dict)} items converted")
print(f"{len(conflicts)} items duplicated")

with open("lemma.en.json", "w") as f:
    json.dump(result_dict, f)