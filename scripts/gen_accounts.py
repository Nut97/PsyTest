from __future__ import annotations
import argparse
import csv
import datetime as dt
import os
import random
import sys
import hashlib
import json
from dataclasses import dataclass
from typing import List, Dict, Optional, Set


#python D:\PsyTest2.0\data\gen_students.py --count 100 --out .\data\Xinya.xlsx

GRADES = ["一年级","二年级","三年级","四年级","五年级","六年级","初一","初二","初三","高一","高二","高三"]
CLASSES = [f"{i}班" for i in range(1, 7)]

# 常见单字姓（子集，足够生成唯一姓名）
COMMON_SURNAMES = list("赵钱孙李周吴郑王冯陈蒋沈韩杨朱秦许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章苏潘葛范彭鲁马方任袁柳鲍史唐费薛雷贺倪汤罗安常乐于时傅齐康伍余顾孟黄穆萧尹姚邵汪祁毛狄贝明臧戴谈宋庞熊纪舒屈项祝董梁杜阮蓝闵席季贾路江童颜郭梅盛林钟徐邱骆高夏蔡田樊胡霍虞柯管卢莫裘邓郁洪左石崔钮龚程邢裴陆荣翁荀")
GIVEN_NAME_CHARS = list("一乙二子文中小大天心安可同宇辰涵杰明佳伟芳霞静丽雪晨凯轩彤语欣萌峰瑜睿琪瑶妍钰豪瑞博逸泽瀚梓耀奕然若溪芷若可欣诗涵子墨浩然子轩雨桐梓萱语汐嘉怡欣怡靖雯梓睿思琦彦霖宸熙子淇钦语宥南亦菲然宁煜航奕航宇航")

AREA_CODES = [
    "110101","110102","110105","120101","310101","320102","330106","340102","350102",
    "360102","370102","410102","420102","430102","440104","440105","440106","450102",
    "500101","510104","520102","530102","610102","620102"
]

WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
CHECK_MAP = ['1','0','X','9','8','7','6','5','4','3','2']

@dataclass
class Student:
    姓名: str
    性别: str
    身份证号: str
    年龄: int
    年级: str
    班级: str
    家长姓名: str
    家长电话: str

def _rand_birthdate_by_age(min_age: int, max_age: int, today: Optional[dt.date]=None) -> dt.date:
    today = today or dt.date.today()
    # 起始：today - max_age 年；结束：today - min_age 年
    start_year = today.year - max_age
    end_year = today.year - min_age
    start = dt.date(start_year, 1, 1)
    end = dt.date(end_year, 12, 31)
    delta_days = (end - start).days
    offset = random.randint(0, max(delta_days, 0))
    return start + dt.timedelta(days=offset)

def _age_from_birthdate(born: dt.date, today: Optional[dt.date]=None) -> int:
    today = today or dt.date.today()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return age

def _calc_check_digit(id17: str) -> str:
    total = sum(int(a) * w for a, w in zip(id17, WEIGHTS))
    return CHECK_MAP[total % 11]

def _make_id_number(sex: str, min_age: int, max_age: int) -> str:
    area = random.choice(AREA_CODES)
    bdate = _rand_birthdate_by_age(min_age, max_age)
    birth = bdate.strftime("%Y%m%d")
    # 顺序码：第17位奇数男、偶数女
    seq_first_two = random.randint(0, 99)
    last_digit = random.randrange(0, 10)
    if sex == "男" and last_digit % 2 == 0:
        last_digit = (last_digit + 1) % 10
    if sex == "女" and last_digit % 2 == 1:
        last_digit = (last_digit + 1) % 10
    seq = f"{seq_first_two:02d}{last_digit}"
    id17 = f"{area}{birth}{seq}"
    check = _calc_check_digit(id17)
    return id17 + check

def _random_chinese_name(existing: Set[str]) -> str:
    for _ in range(2000):
        surname = random.choice(COMMON_SURNAMES)
        given_len = 1 if random.random() < 0.4 else 2
        given = "".join(random.choice(GIVEN_NAME_CHARS) for _ in range(given_len))
        name = surname + given
        if name not in existing:
            return name
    return surname + given + random.choice(GIVEN_NAME_CHARS)

def _random_phone(existing: Set[str]) -> str:
    for _ in range(20000):
        second = random.choice(list("3456789"))
        rest = random.randint(10_000_000, 99_999_999)
        phone = f"1{second}{rest:08d}"
        if phone not in existing:
            return phone
    raise RuntimeError("无法生成更多唯一手机号")

def _load_first_column_names(path: str) -> List[str]:
    ext = os.path.splitext(path)[1].lower()
    names: List[str] = []
    try:
        if ext in (".xlsx", ".xls"):
            import pandas as pd  # type: ignore
            df = pd.read_excel(path)
            first_col = df.columns[0]
            for v in df[first_col].dropna().astype(str).tolist():
                v = v.strip()
                if v:
                    names.append(v)
        elif ext == ".csv":
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row:
                        continue
                    v = (row[0] or "").strip()
                    if v:
                        names.append(v)
        else:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    v = line.strip()
                    if v:
                        names.append(v)
    except Exception as e:
        print(f"[WARN] 读取姓名种子失败：{e}", file=sys.stderr)
    # 去重保持顺序
    seen, uniq = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq

def generate_records(count: int, names_seed: Optional[List[str]]=None, min_age: int=5, max_age: int=25, seed: Optional[int]=None) -> List[Dict[str, str]]:
    if seed is not None:
        random.seed(seed)
    names_seed = names_seed or []
    out: List[Dict[str, str]] = []
    used_names: Set[str] = set()
    used_phones: Set[str] = set()
    used_ids: Set[str] = set()

    # 先用种子
    for base_name in names_seed:
        if len(out) >= count:
            break
        name = base_name.strip()
        if not name or name in used_names:
            continue
        sex = random.choice(["男", "女"])
        idno = _make_id_number(sex, min_age, max_age)
        while idno in used_ids:
            idno = _make_id_number(sex, min_age, max_age)
        birth_year = int(idno[6:10]); birth_month = int(idno[10:12]); birth_day = int(idno[12:14])
        age = _age_from_birthdate(dt.date(birth_year, birth_month, birth_day))
        grade = random.choice(GRADES)
        klass = random.choice(CLASSES)
        relation = random.choice(["父亲","母亲"])
        parent_name = f"{name}{relation}"
        phone = _random_phone(used_phones)

        used_names.add(name); used_ids.add(idno); used_phones.add(phone)

        out.append({
            "姓名": name, "性别": sex, "身份证号": idno, "年龄": age,
            "年级": grade, "班级": klass, "家长姓名": parent_name, "家长电话": phone
        })

    # 随机补齐
    while len(out) < count:
        name = _random_chinese_name(used_names)
        sex = random.choice(["男", "女"])
        idno = _make_id_number(sex, min_age, max_age)
        while idno in used_ids:
            idno = _make_id_number(sex, min_age, max_age)
        birth_year = int(idno[6:10]); birth_month = int(idno[10:12]); birth_day = int(idno[12:14])
        age = _age_from_birthdate(dt.date(birth_year, birth_month, birth_day))
        grade = random.choice(GRADES)
        klass = random.choice(CLASSES)
        relation = random.choice(["父亲","母亲"])
        parent_name = f"{name}{relation}"
        phone = _random_phone(used_phones)

        used_names.add(name); used_ids.add(idno); used_phones.add(phone)

        out.append({
            "姓名": name, "性别": sex, "身份证号": idno, "年龄": age,
            "年级": grade, "班级": klass, "家长姓名": parent_name, "家长电话": phone
        })
    return out

# ------- 新增：密码加密 & JSON 输出 -------

def _encrypt_password_from_id(idno: str) -> str:
    """根据身份证号生成密码：sha1Hex(md5Hex(身份证后六位))"""
    tail = idno[-6:]
    md5_hex = hashlib.md5(tail.encode("utf-8")).hexdigest()
    sha1_hex = hashlib.sha1(md5_hex.encode("utf-8")).hexdigest()
    return sha1_hex

def _write_json_accounts(rows: List[Dict[str, str]], out_path: str):
    """根据 rows 生成账号 JSON 文件：数据集名称 / studentNum / password"""
    base, _ = os.path.splitext(out_path)
    json_path = base + ".json"

    data = []
    for idx, r in enumerate(rows, start=1):
        idno = str(r["身份证号"])
        item = {
            "数据集名称": f"数据{idx}",
            "studentNum": idno,
            "password": _encrypt_password_from_id(idno),
        }
        data.append(item)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"已写入 JSON：{json_path}")

# ------- 原 CSV / Excel 输出，表头加 * -------

def _write_output(rows: List[Dict[str, str]], out_path: str):
    out_path = out_path or "./students.csv"

    # 内部字段名（必须和 rows 里的 key 一致）
    cols = ["姓名","性别","身份证号","年龄","年级","班级","家长姓名","家长电话"]
    # 表头显示名：给指定字段加 *
    header_cols = ["*姓名","*性别","*身份证号","年龄","*年级","*班级","家长姓名","家长电话"]

    ext = os.path.splitext(out_path)[1].lower()
    if ext == ".xlsx":
        try:
            import pandas as pd  # type: ignore
            import warnings
            warnings.filterwarnings("ignore", category=UserWarning)
            df = pd.DataFrame(rows, columns=cols)
            df.columns = header_cols
            df.to_excel(out_path, index=False)
            print(f"已写入 Excel：{out_path}")
            return
        except Exception as e:
            print(f("[WARN] 写入Excel失败({e})，改写CSV"))
            ext = ".csv"
            out_path = os.path.splitext(out_path)[0] + ".csv"

    # CSV
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        header_writer = csv.writer(f)
        header_writer.writerow(header_cols)
        writer = csv.DictWriter(f, fieldnames=cols)
        for r in rows:
            writer.writerow(r)
    print(f"已写入 CSV：{out_path}")

def main():
    parser = argparse.ArgumentParser(description="随机生成学生测试数据")
    parser.add_argument("--count", type=int, required=True, help="生成记录数量")
    parser.add_argument("--infile", type=str, default=None, help="可选：Excel/CSV/文本；第一列作为学生姓名")
    parser.add_argument("--out", type=str, default="./students.csv", help="输出文件路径（.csv 或 .xlsx）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子(可复现)")
    parser.add_argument("--min-age", type=int, default=5, help="最小年龄")
    parser.add_argument("--max-age", type=int, default=25, help="最大年龄")
    args = parser.parse_args()

    names_seed: List[str] = []
    if args.infile:
        names_seed = _load_first_column_names(args.infile)

    rows = generate_records(
        count=args.count,
        names_seed=names_seed,
        min_age=args.min_age,
        max_age=args.max_age,
        seed=args.seed
    )

    # 表格
    _write_output(rows, args.out)
    # JSON 账号文件
    _write_json_accounts(rows, args.out)

if __name__ == "__main__":
    main()
