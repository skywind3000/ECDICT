import csv
import sqlite3
from pathlib import Path, PurePath

import stardict

MYSQLITE = 'ecdictSqlite.db'


def new_inflection(exchange):
    """去除ECDICT exchange字段中冗余的f:复数， b:比较级， z:最高级。如果与对应标
    签内容不同，则予以保留。

    Note:
        ecdict exchange列中0: 代表Lemma，如 perceived 的 Lemma 是 perceive

        类型 	说明
        p 	过去式（did）
        d 	过去分词（done）
        i 	现在分词（doing）
        3 	第三人称单数（does）
        r 	形容词比较级（-er）
        t 	形容词最高级（-est）
        s 	名词复数形式
        0 	Lemma，如 perceived 的 Lemma 是 perceive
        1 	Lemma 的变换形式，比如 s 代表 apples 是其 lemma 的复数形式

        https://github.com/skywind3000/ECDICT/issues/23

    """

    if len(exchange) == 0:
        return ''
    lists = exchange.split('/')

    inflection = {}

    for trans in lists:
        inflection[trans[0]] = trans[2:]

    old_new = {'b': 'r', 'z': 't', 'f': 's'}
    # 只去除相应重复值。如不重复的话，仍保留b, z, f标签。
    for i in old_new:
        if inflection.get(i):
            if not inflection.get(old_new[i]):
                inflection[old_new[i]] = inflection[i]
                inflection.pop(i)
            elif inflection[old_new[i]] == inflection[i]:
                inflection.pop(i)

    newexchange = []
    for i in inflection:
        newexchange.append(i + ':' + inflection[i])

    return ('/').join(newexchange)


def init_ecdict_sqlite():

    stardict.convert_dict(MYSQLITE, 'ecdict.csv')
    con = sqlite3.connect(MYSQLITE)
    cur = con.cursor()

    # 查询所有行的数据
    select_query = "SELECT word, exchange FROM stardict"
    cur.execute(select_query)
    rows = cur.fetchall()

    # 遍历每一行，根据 word和exchange 的值更新新建列lemma
    for row in rows:
        word = row[0]
        exchange = row[1]

        inflection = new_inflection(exchange)

        update_query = "UPDATE stardict SET exchange = ? WHERE word = ?"
        cur.execute(update_query, (inflection, word))

    con.commit()
    con.close()


init_ecdict_sqlite()  # 只需运行一次，生成sqlite3 db文件

# 转换SQLITE为csv文件
stardict.convert_dict('ecdict.csv', MYSQLITE)
