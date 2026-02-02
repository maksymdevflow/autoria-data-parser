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

# Відображення категорії батьківського лінка (Link.car_type) на набір констант для TruckMarket.
# Поки тільки 3.5т; коли зʼявляться format_5_15t_* — додати "5-15 тон": CONSTANTS_5_15T.
CONSTANTS_BY_CATEGORY = {
    "3-5 тон": CONSTANTS_3_5T,
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
