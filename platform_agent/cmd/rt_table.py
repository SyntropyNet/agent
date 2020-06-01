from pathlib import Path

RT_TABLE_PATH = "/etc/iproute2/rt_tables"


def read_rt_table():
    path = "/etc/iproute2/rt_tables"
    rt_table = Path(path)
    res = rt_table.read_text()
    rt_table_dict = {}
    for line in res.splitlines():
        if line[0] == "#":
            continue
        line = line.strip()
        line.replace('\t', ' ')
        res = line.split()
        if len(res) >= 2 and res[0].isdigit():
            rt_table_dict[res[0]] = {'name': res[1]}
    return rt_table_dict


def insert_rt_table(table_id, name):
    path = "/etc/iproute2/rt_tables"
    with open(path, 'a') as rt_table:
        rt_table.write(f'{table_id} {name}\n')


def delete_rt_table(table_id, name):
    with open(RT_TABLE_PATH, "r") as f:
        lines = f.readlines()
    with open(RT_TABLE_PATH, "w") as f:
        for line in lines:
            if line != f'{table_id} {name}\n':
                f.write(line)


def get_available_rt_table():
    table = read_rt_table()
    for i in range(1, 252):
        if table.get(str(i)) == None:
            return str(i)
