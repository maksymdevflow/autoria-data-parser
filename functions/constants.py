format_3_5t_brands = {
    "1055": "Mercedes-Benz",
    "1109": "Volkswagen",
    "1069": "Opel",
    "1071": "Peugeot",
    "1081": "Renault",
    "1007": "Fiat",
    "1009": "Ford",
    "1065": "Nissan",
    "1107": "Toyota",
    "1117": "ГАЗ",
    "4034": "Iveco",
    "4222": "Citroen",
}

format_3_5t_models = {
    "1055": {  # Mercedes-Benz
        "146": "Citan",
        "148": "Metris",
        "145": "Sprinter",
        "147": "Vario",
        "38": "Viano",
        "39": "Vito",
        "149": "eVito",
    },
    "1109": {  # Volkswagen
        "45": "Caddy",
        "43": "Crafter",
        "46": "LT",
        "47": "Multivan",
        "44": "Transporter",
        "48": "Vito",
    },
    "1069": {  # Opel
        "44": "Arena",
        "43": "Astra",
        "41": "Combo",
        "40": "Combo Cargo",
        "39": "Combo-e",
        "38": "Movano",
        "37": "Vivaro",
        "42": "Vivaro-e",
    },
    "1071": {  # Peugeot
        "62": "Bipper",
        "61": "Boxer",
        "63": "E-Partner",
        "59": "Expert",
        "60": "Partner",
    },
    "1081": {  # Renault
        "58": "Dokker",
        "59": "Express",
        "63": "Express",
        "62": "Express Van",
        "54": "Kangoo",
        "61": "Logan Van",
        "60": "Mascott",
        "55": "Master",
        "57": "Trafic",
    },
    "1007": {  # Fiat
        "2": "Doblo",
        "1": "Ducato",
        "3": "Fiorino",
        "6": "Qubo",
        "4": "Scudo",
        "5": "Talento",
    },
    "1009": {  # Ford
        "5": "Courier",
        "1": "Transit",
        "3": "Transit Connect",
        "4": "Transit Courier",
        "2": "Transit Custom",
    },
    "1065": {  # Nissan
        "10": "Interstar",
        "13": "Kubistar",
        "131": "NV",
        "11": "NV1500",
        "4": "NV200",
        "12": "NV2500",
        "6": "NV300",
        "161": "NV350",
        "3": "NV400",
        "8": "Primastar",
        "9": "Townstar Van",
        "1": "e-NV200",
    },
    "1107": {  # Toyota
        "3": "Hiace",
        "2": "Proace",
        "1": "Proace City",
    },
    "1117": {  # ГАЗ
        "66": "18",
        "75": "25",
        "15": "2705 Газель",
        "16": "2752 Соболь",
        "22": "3302 Газель",
        "69": "46",
        "70": "61",
        "36": "66",
        "26": "3307",
        "27": "3309",
        "35": "4301",
        "28": "33104",
        "37": "Next",
        "38": "САЗ 3507",
    },
    "4034": {  # Iveco
        "66": "18",
        "75": "25",
        "15": "2705 Газель",
        "16": "2752 Соболь",
        "22": "3302 Газель",
        "69": "46",
        "70": "61",
        "36": "66",
        "26": "3307",
        "27": "3309",
        "35": "4301",
        "28": "33104",
        "37": "Next",
        "38": "САЗ 3507",
    },
    "4222": {  # Citroen
        "2": "Berlingo",
        "3": "Dispatch",
        "1": "Jumper",
        "4": "Jumpy",
        "5": "Nemo",
        "6": "С25",
        "7": "С35",
    },
}


f_format_3_5t = {
    "f1": "Тип кузова",
    "f3": "Пальне",
    "f4": "Потужність двигуна",
    "f5": "Технічний стан",
    "f7": "Рік випуску",
    "f8": "Модель",
    "f9": "Обʼєм двигуна",
    "f10": "Пробіг, тис. км",
    "f12": "Коробка передач",
    "f13": "Колір",
    "f14": "Привід",
}

format_3_5t_body_types = {
    "1": ["Фургон", "Вантажний фургон"],
    "2": ["Вантажопасажирський фургон"],
    "4": ["Тентований"],
    "5": ["Рефрижератор"],
    "6": ["Автовоз"],
    "7": ["Борт"],
    "8": ["Мікроавтобус", "Мікроавтобус вантажний (до 3,5т)"],
}


format_3_5t_fuel_types = {
    "1": "Бензин",
    "2": "Дизель",
    "5": "Електро",
    "6": "Газ",
}

format_3_5t_transmission_types = {
    "1": "Ручна / Механіка",
    "2": "Автомат",
    "3": "Типтронік",
    "4": "Робот",
    "5": "Варіатор",
}

format_3_5t_color_types = {
    "1": "Коричневий",
    "2": "Чорний",
    "3": "Зелений",
    "4": "Сірий",
    "5": "Помаранчевий",
    "6": "Синій",
    "7": "Фіолетовий",
    "8": "Червоний",
    "9": "Бежевий",
    "10": "Білий",
    "11": "Жовтий",
}

format_3_5t_drive_types = {"1": "Передній", "2": "Задній", "3": "Повний"}

format_3_5t_technical_condition_types = {"1": "Б/В", "2": "Новий", "3": "На запчастини"}

# Набір констант для категорії 3.5т (Link.car_type = "3-5 тон" тощо).
# У майбутньому: format_5_15t_* та CONSTANTS_BY_CATEGORY["5-15 тон"].
CONSTANTS_3_5T = {
    "brands": format_3_5t_brands,
    "models": format_3_5t_models,
    "body_types": format_3_5t_body_types,
    "fuel_types": format_3_5t_fuel_types,
    "transmission_types": format_3_5t_transmission_types,
    "color_types": format_3_5t_color_types,
    "drive_types": format_3_5t_drive_types,
    "technical_condition_types": format_3_5t_technical_condition_types,
}
format_5_15t_models = {
    "4026": {
        "147": "45",
        "148": "75",
        "150": "85",
        "152": "95",
        "151": "AE",
        "39": "CF",
        "149": "FA",
        "145": "FT",
        "146": "LF",
        "38": "XF"
    },
    "4027": {
        "38": "Daily",
        "39": "EuroCargo",
        "146": "Stralis",
        "145": "eDaily"
    },
    "4028": {
        "147": "Comandor",
        "39": "LE",
        "38": "TGL",
        "145": "TGM",
        "146": "TGS"
    },
    "4029": {
        "145": "Actros",
        "148": "Antos",
        "38": "Atego",
        "39": "Axor",
        "147": "SK-Series",
        "149": "Sprinter",
        "146": "Vario"
    },
    "4030": {
        "145": "D-Series",
        "149": "Kerax",
        "38": "Magnum",
        "146": "Maxity",
        "148": "Midliner",
        "39": "Midlum",
        "147": "Premium"
        },
    "4031": {
        "147": "F",
        "38": "FH",
        "146": "FL",
        "39": "FM",
        "145": "V"
    },
    "4032": {
        "145": "52",
        "38": "53",
        "146": "3302",
        "147": "3307",
        "39": "5204"
    },
    "4033": {
        "145": "5320",
        "147": "5320",
        "146": "5410",
        "38": "53212",
        "148": "55102",
        "39": "55111"
    },
    "4047": {
        "38": "815",
        "146": "8152",
        "147": "Phoenix",
        "145": "T-815"
        },
    "4220": {
        "1": "130",
        "2": "131",
        "3": "157",
        "4": "4331",
        "5": "ММЗ 554",
        "6": "133",
        "7": "5301",
        "8": "4505",
        "9": "4502",
        "10": "45085",
        "11": "431410",
        "12": "ММЗ 45021",
        "13": "431412",
        "14": "4329",
        "15": "45023",
        "16": "ММЗ 4502",
        "17": "ММЗ 555",
        "18": "ММЗ",
        "19": "431610",
        "20": "4517",
        "21": "4131",
        "22": "ММЗ 34502",
        "23": "138А",
        "24": "441510",
        "25": "433362"
        },
    "4221": {
        "3": "Dexen",
        "4": "Gixen",
        "5": "Kuxen",
        "6": "Maxen",
        "1": "Maximus",
        "2": "Novus",
        "7": "Prima"
        }
}

format_5_15t_brands={
    "4026": "DAF",
    "4027": "Iveco",
    "4028": "MAN",
    "4029": "Mercedes-Benz",
    "4030": "Renault",
    "4031": "Volvo",
    "4032": "ГАЗ",
    "4033": "КамАЗ",
    "4047": "TATRA",
    "4220": "ЗИЛ",
    "4221": "Daewoo Trucks"
}

format_5_15t_body_types = {
    "1": ["Будка", "Вантажний фургон"],
    "2": ["Рефрижератор"],
    "3": ["Контейнеровоз"],
    "4": ["Тентований"],
    "5": ["Самоскид"],
    "6": ["Бортовий"],
    "7": ["Автовоз"]
}

format_5_15t_fuel_types = {
    "1": "Бензин",
    "2": "Дизель",
    "5": "Електро",
    "6": "Газ",
    "7": "Газ + бензин"
}
format_5_15t_transmission_types = {
    "1": "Ручна / Механіка",
    "2": "Автомат",
    "4": "Робот",
    "5": "Варіатор",
    "3": "Типтронік"
}

format_5_15t_color_types = {
    "9": "Бежевий",
    "2": "Чорний",
    "6": "Синій",
    "1": "Коричневий",
    "3": "Зелений",
    "4": "Сірий",
    "5": "Помаранчевий",
    "7": "Фіолетовий",
    "8": "Червоний",
    "10": "Білий",
    "11": "Жовтий"
}

format_5_15t_drive_types = {
    "1": "Передній",
    "2": "Задній",
    "3": "Повний"
}

format_5_15t_technical_condition_types = None

CONSTANTS_5_15T={
    "brands": format_5_15t_brands,
    "models": format_5_15t_models,
    "body_types": format_5_15t_body_types,
    "fuel_types": format_5_15t_fuel_types,
    "transmission_types": format_5_15t_transmission_types,
    "color_types": format_5_15t_color_types,
    "drive_types": format_5_15t_drive_types,
    "technical_condition_types": format_5_15t_technical_condition_types
}

CONSTANTS_BY_CATEGORY = {
    "3-5 тон": CONSTANTS_3_5T,
    "5-15 тон": CONSTANTS_5_15T,
    # "5-15 тон": CONSTANTS_5_15T,  # майбутнє
    # "Тягач +": CONSTANTS_...,     # майбутнє
}


def get_constants_for_category(link_car_type: str | None) -> dict:
    """
    Повертає набір констант (brands, models, body_types, …) для інтеграції TruckMarket
    за категорією батьківського лінка (Link.car_type).
    Якщо категорія невідома або None — використовується 3.5т.
    """
    key = (link_car_type or "").strip()
    if not key:
        return CONSTANTS_3_5T
    return CONSTANTS_BY_CATEGORY.get(key, CONSTANTS_3_5T)
