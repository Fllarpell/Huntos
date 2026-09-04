/** Shared Hunt cities. HH area ids — keep in sync with backend ``geo.py``. */

export const RUSSIA_AREA = "113";

export const SEARCH_CITIES = [
  { value: "113", label: "Россия" },
  { value: "1", label: "Москва" },
  { value: "2", label: "Санкт-Петербург" },
  { value: "14", label: "Архангельск" },
  { value: "15", label: "Астрахань" },
  { value: "11", label: "Барнаул" },
  { value: "17", label: "Белгород" },
  { value: "67", label: "Великий Новгород" },
  { value: "22", label: "Владивосток" },
  { value: "23", label: "Владимир" },
  { value: "24", label: "Волгоград" },
  { value: "26", label: "Воронеж" },
  { value: "3", label: "Екатеринбург" },
  { value: "2088", label: "Зеленоград" },
  { value: "96", label: "Ижевск" },
  { value: "2734", label: "Иннополис" },
  { value: "35", label: "Иркутск" },
  { value: "88", label: "Казань" },
  { value: "41", label: "Калининград" },
  { value: "43", label: "Калуга" },
  { value: "47", label: "Кемерово" },
  { value: "53", label: "Краснодар" },
  { value: "54", label: "Красноярск" },
  { value: "56", label: "Курск" },
  { value: "58", label: "Липецк" },
  { value: "1399", label: "Магнитогорск" },
  { value: "1002", label: "Минск" },
  { value: "64", label: "Мурманск" },
  { value: "1641", label: "Набережные Челны" },
  { value: "66", label: "Нижний Новгород" },
  { value: "1240", label: "Новокузнецк" },
  { value: "4", label: "Новосибирск" },
  { value: "68", label: "Омск" },
  { value: "70", label: "Оренбург" },
  { value: "71", label: "Пенза" },
  { value: "72", label: "Пермь" },
  { value: "76", label: "Ростов-на-Дону" },
  { value: "77", label: "Рязань" },
  { value: "78", label: "Самара" },
  { value: "79", label: "Саратов" },
  { value: "83", label: "Смоленск" },
  { value: "237", label: "Сочи" },
  { value: "1381", label: "Сургут" },
  { value: "89", label: "Тверь" },
  { value: "90", label: "Томск" },
  { value: "92", label: "Тула" },
  { value: "95", label: "Тюмень" },
  { value: "98", label: "Ульяновск" },
  { value: "99", label: "Уфа" },
  { value: "102", label: "Хабаровск" },
  { value: "107", label: "Чебоксары" },
  { value: "104", label: "Челябинск" },
  { value: "112", label: "Ярославль" },
] as const;

/** First row in the search form. The rest are behind «ещё» + typeahead. */
export const SEARCH_CITY_HUBS = [
  RUSSIA_AREA,
  "1",
  "2",
  "3",
  "4",
  "88",
  "66",
  "53",
  "76",
  "2734",
] as const;

/** Россия = вся страна. Города с ней не живут в одном выборе. */
export function nextSearchCities(prev: readonly string[], next: readonly string[]): string[] {
  const added = next.filter((id) => !prev.includes(id));
  if (added.includes(RUSSIA_AREA)) return [RUSSIA_AREA];
  const cities = next.filter((id) => id !== RUSSIA_AREA);
  return cities.length ? [...cities] : [RUSSIA_AREA];
}
