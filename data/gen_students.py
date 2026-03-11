from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import sys
from typing import Optional


GRADES = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三']
CLASSES = [f'{index}班' for index in range(1, 7)]
COMMON_SURNAMES = list('赵钱孙李周吴郑王冯陈蒋沈韩杨朱秦许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章苏潘葛范彭鲁马方任袁柳鲍史唐费薛雷贺倪汤罗安常乐于时傅齐康伍余顾孟黄穆萧尹姚邵汪祁毛狄贝明臧戴谈宋庞熊纪舒屈项祝董梁杜阮蓝闵席季贾路江童颜郭梅盛林钟徐邱骆高夏蔡田樊胡霍虞柯管卢莫裘邓郁洪左石崔钮龚程邢裴陆荣翁荀')
GIVEN_NAME_CHARS = list('一乙二子文中小大天心安可同宇辰涵杰明佳伟芳霞静丽雪晨凯轩彤语欣萌峰瑜睿琪瑶妍钰豪瑞博逸泽瀚梓耀奕然若溪芷若可欣诗涵子墨浩然子轩雨桐梓萱语汐嘉怡欣怡靖雯梓睿思琦彦霖宸熙子淇钦语宥南亦菲然宁煜航奕航宇航')
AREA_CODES = [
    '110101', '110102', '110105', '120101', '310101', '320102', '330106', '340102', '350102',
    '360102', '370102', '410102', '420102', '430102', '440104', '440105', '440106', '450102',
    '500101', '510104', '520102', '530102', '610102', '620102',
]
WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
CHECK_MAP = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']


def _rand_birthdate_by_age(min_age: int, max_age: int, today: Optional[dt.date] = None) -> dt.date:
    today = today or dt.date.today()
    start = dt.date(today.year - max_age, 1, 1)
    end = dt.date(today.year - min_age, 12, 31)
    offset = random.randint(0, max((end - start).days, 0))
    return start + dt.timedelta(days=offset)


def _age_from_birthdate(born: dt.date, today: Optional[dt.date] = None) -> int:
    today = today or dt.date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _calc_check_digit(id17: str) -> str:
    total = sum(int(value) * weight for value, weight in zip(id17, WEIGHTS))
    return CHECK_MAP[total % 11]


def _make_id_number(sex: str, min_age: int, max_age: int) -> str:
    area = random.choice(AREA_CODES)
    birthdate = _rand_birthdate_by_age(min_age, max_age)
    birth = birthdate.strftime('%Y%m%d')
    seq_first_two = random.randint(0, 99)
    last_digit = random.randrange(0, 10)
    if sex == '男' and last_digit % 2 == 0:
        last_digit = (last_digit + 1) % 10
    if sex == '女' and last_digit % 2 == 1:
        last_digit = (last_digit + 1) % 10
    id17 = f'{area}{birth}{seq_first_two:02d}{last_digit}'
    return id17 + _calc_check_digit(id17)


def _random_name(used_names: set[str]) -> str:
    for _ in range(2000):
        surname = random.choice(COMMON_SURNAMES)
        given = ''.join(random.choice(GIVEN_NAME_CHARS) for _ in range(1 if random.random() < 0.4 else 2))
        candidate = surname + given
        if candidate not in used_names:
            return candidate
    return surname + given + random.choice(GIVEN_NAME_CHARS)


def _random_phone(used_phones: set[str]) -> str:
    for _ in range(20000):
        phone = '1' + random.choice(list('3456789')) + f'{random.randint(100_000_000, 999_999_999):09d}'
        if phone not in used_phones:
            return phone
    raise RuntimeError('无法生成更多唯一手机号')


def _load_first_column_names(path: str) -> list[str]:
    extension = os.path.splitext(path)[1].lower()
    names: list[str] = []
    try:
        if extension in {'.xlsx', '.xls'}:
            import pandas as pd  # type: ignore

            frame = pd.read_excel(path)
            first_column = frame.columns[0]
            names = [str(value).strip() for value in frame[first_column].dropna().tolist() if str(value).strip()]
        elif extension == '.csv':
            with open(path, 'r', encoding='utf-8-sig') as file:
                reader = csv.reader(file)
                names = [str(row[0]).strip() for row in reader if row and str(row[0]).strip()]
        else:
            with open(path, 'r', encoding='utf-8') as file:
                names = [line.strip() for line in file if line.strip()]
    except Exception as exc:
        print(f'[WARN] 读取姓名种子失败：{exc}', file=sys.stderr)
    seen: set[str] = set()
    unique_names: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            unique_names.append(name)
    return unique_names


def generate_records(
    count: int,
    *,
    names_seed: list[str] | None = None,
    min_age: int = 5,
    max_age: int = 25,
    seed: int | None = None,
) -> list[dict[str, str | int]]:
    if seed is not None:
        random.seed(seed)
    names_seed = names_seed or []
    rows: list[dict[str, str | int]] = []
    used_names: set[str] = set()
    used_phones: set[str] = set()
    used_ids: set[str] = set()

    def append_record(name: str) -> None:
        sex = random.choice(['男', '女'])
        id_number = _make_id_number(sex, min_age, max_age)
        while id_number in used_ids:
            id_number = _make_id_number(sex, min_age, max_age)
        birth_year, birth_month, birth_day = int(id_number[6:10]), int(id_number[10:12]), int(id_number[12:14])
        age = _age_from_birthdate(dt.date(birth_year, birth_month, birth_day))
        record = {
            '姓名': name,
            '性别': sex,
            '身份证号': id_number,
            '年龄': age,
            '年级': random.choice(GRADES),
            '班级': random.choice(CLASSES),
            '家长姓名': f"{name}{random.choice(['父亲', '母亲'])}",
            '家长电话': _random_phone(used_phones),
        }
        rows.append(record)
        used_names.add(name)
        used_ids.add(id_number)
        used_phones.add(str(record['家长电话']))

    for raw_name in names_seed:
        if len(rows) >= count:
            break
        name = raw_name.strip()
        if name and name not in used_names:
            append_record(name)

    while len(rows) < count:
        append_record(_random_name(used_names))
    return rows


def _encrypt_password_from_id(id_number: str) -> str:
    tail = id_number[-6:]
    md5_hex = hashlib.md5(tail.encode('utf-8')).hexdigest()
    return hashlib.sha1(md5_hex.encode('utf-8')).hexdigest()


def _write_json_accounts(rows: list[dict[str, str | int]], out_path: str) -> None:
    base, _ = os.path.splitext(out_path)
    json_path = base + '.json'
    payload = []
    for index, row in enumerate(rows, start=1):
        payload.append(
            {
                '数据集名称': f'数据{index}',
                'studentNum': str(row['身份证号']),
                'password': _encrypt_password_from_id(str(row['身份证号'])),
            }
        )
    with open(json_path, 'w', encoding='utf-8') as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    print(f'已写入 JSON：{json_path}')


def _write_output(rows: list[dict[str, str | int]], out_path: str) -> None:
    out_path = out_path or './students.csv'
    columns = ['姓名', '性别', '身份证号', '年龄', '年级', '班级', '家长姓名', '家长电话']
    header_columns = ['*姓名', '*性别', '*身份证号', '年龄', '*年级', '*班级', '家长姓名', '家长电话']
    extension = os.path.splitext(out_path)[1].lower()
    if extension == '.xlsx':
        try:
            import pandas as pd  # type: ignore

            frame = pd.DataFrame(rows, columns=columns)
            frame.columns = header_columns
            frame.to_excel(out_path, index=False)
            print(f'已写入 Excel：{out_path}')
            return
        except Exception as exc:
            print(f'[WARN] 写入 Excel 失败（{exc}），改写 CSV')
            out_path = os.path.splitext(out_path)[0] + '.csv'

    with open(out_path, 'w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(header_columns)
        data_writer = csv.DictWriter(file, fieldnames=columns)
        for row in rows:
            data_writer.writerow(row)
    print(f'已写入 CSV：{out_path}')


def main() -> None:
    parser = argparse.ArgumentParser(description='随机生成学生测试数据')
    parser.add_argument('--count', type=int, required=True, help='生成记录数量')
    parser.add_argument('--infile', type=str, default=None, help='可选：Excel / CSV / 文本，第一列作为学生姓名')
    parser.add_argument('--out', type=str, default='./students.csv', help='输出文件路径（.csv 或 .xlsx）')
    parser.add_argument('--seed', type=int, default=None, help='随机种子')
    parser.add_argument('--min-age', type=int, default=5, help='最小年龄')
    parser.add_argument('--max-age', type=int, default=25, help='最大年龄')
    args = parser.parse_args()

    names_seed = _load_first_column_names(args.infile) if args.infile else []
    rows = generate_records(
        args.count,
        names_seed=names_seed,
        min_age=args.min_age,
        max_age=args.max_age,
        seed=args.seed,
    )
    _write_output(rows, args.out)
    _write_json_accounts(rows, args.out)


if __name__ == '__main__':
    main()