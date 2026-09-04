export type GuideCopy = {
  title: string;
  body: string;
};

/** Short how-to for each section and field. Ids match GuideSpot / GuideHint. */
export const GUIDE: Record<string, GuideCopy> = {
  "shell.hunt": {
    title: "Охота",
    body: "Охота — это тезис: какой сегмент проверяешь. Inbox, воронка и тезис показывают карточки этой охоты. «Все карточки» — без фильтра.",
  },
  "shell.nav": {
    title: "Разделы",
    body: "Inbox — новые вакансии. Воронка — куда сдвинул. Время — собесы и пинги. Контакты — HR. Стажировки — программы и школы. Тезис — жив ли сегмент. Настройки — поиски и резюме.",
  },
  "shell.guide": {
    title: "Обучение этой страницы",
    body: "Внизу слева. Имя экрана под кнопкой — Inbox, Воронка, Настройки. Это разные прохождения, не одно на всё HuntOS.",
  },
  "shell.workspace": {
    title: "Аккаунт",
    body: "Свой inbox и воронка.",
  },
  "shell.chat": {
    title: "Диалоги",
    body: "Переписка с админом. В шапке видно, на сайте он или нет и когда был. Админ отвечает из тех же Диалогов.",
  },

  "inbox.header": {
    title: "Inbox",
    body: "Сюда падают вакансии из поисков, Telegram и клиппера. Это не воронка: пока не сдвинешь, карточка просто лежит в ленте.",
  },
  "inbox.corridor": {
    title: "Зарплатный рынок",
    body: "Вилка по скачанным вакансиям и зарплатным агрегаторам. В Inbox свёрнута в полоску — источники открываются поверх ленты. Грейд и специальность сужают ту же смесь. Это статистика, не оффер.",
  },
  "inbox.sort": {
    title: "Сортировка",
    body: "Условия — свежие за сутки, потом зарплата. Новизна и грейд — другие порядки той же ленты.",
  },
  "inbox.filters": {
    title: "Фильтры",
    body: "Панель поверх ленты, список не уезжает. Грейд, формат, площадка и стек — чипами. Нажми чип ещё раз, кликни мимо или «сбросить».",
  },
  "inbox.search": {
    title: "Поиск по ленте",
    body: "«go» или «frontend» режут по стеку собранных карточек. Можно дописать компанию: «go яндекс». Ищет ещё по роли, @hr и имени сохранённого поиска.",
  },
  "inbox.add": {
    title: "Ручная вакансия",
    body: "Карточка сразу в Inbox текущей охоты. Удобно, если вакансию прислали в личку, а не нашли поиском.",
  },
  "inbox.grade": {
    title: "Грейд в ленте",
    body: "Режет уже скачанные карточки. Поиски в Настройках от этого не меняются.",
  },
  "inbox.format": {
    title: "Формат в ленте",
    body: "Удалёнка, офис, гибрид — как в карточке. Пусто — любой.",
  },
  "inbox.more": {
    title: "Ещё фильтры",
    body: "NDA, вилка и площадка, с которой карточка приехала.",
  },
  "inbox.except": {
    title: "Кроме компаний",
    body: "Яндекс, Yandex и «Яндекс.Такси» — одно имя. Enter или запятая. Только эта лента, тезис не трогает.",
  },
  "inbox.searches": {
    title: "Какой поиск собрал",
    body: "Какой сохранённый поиск привёз карточку. Имена без «весь IT». «Ещё» — остальные сайты компаний.",
  },
  "inbox.stack": {
    title: "Стек в ленте",
    body: "Языки сразу, роли и QA за «ещё». Режут уже скачанное. То же слово можно набрать в поиске сверху.",
  },
  "inbox.list": {
    title: "Лента",
    body: "Клик открывает карточку. Чекбоксы — пачка в воронку или в корзину. Клавиши: j/k список, Enter открыть, e в работу, x в корзину, пробел отметить.",
  },

  "pipeline.header": {
    title: "Воронка",
    body: "Стадии после Inbox: откликнуться → жду ответа → скрининг → тех. собес → оффер. Отказ — отдельная колонка, не корзина.",
  },
  "pipeline.search": {
    title: "Поиск по доске",
    body: "/ или Cmd+K — фокус в поиск. Стрелки по результатам, Enter открыть, R — отказ. Escape сбрасывает запрос.",
  },
  "pipeline.mass": {
    title: "Нагрузка",
    body: "Столбики — сколько карточек в каждой стадии. Янтарный — пора пингануть.",
  },
  "pipeline.nudge": {
    title: "Пингануть",
    body: "Очередь из «жду ответа». Отметь «пинганул» — таймер сбросится.",
  },
  "pipeline.board": {
    title: "Колонки",
    body: "Перетащи карточку или стрелки на ней. «inbox» возвращает в ленту. Охота сверху сужает доску до одного тезиса.",
  },

  "time.header": {
    title: "Время",
    body: "Сетка шагов из карточек: скрининг, собес, тех задание, дедлайн оффера и слоты пинга. Это календарь охоты, не список заявок.",
  },
  "time.range": {
    title: "День / неделя / месяц",
    body: "Тот же набор событий, разный масштаб. «Сегодня» возвращает курсор. Стрелки листают период.",
  },
  "time.grid": {
    title: "Сетка",
    body: "Клик по событию открывает карточку. Пусто — в вакансии ещё нет шага с датой.",
  },

  "contacts.header": {
    title: "Контакты",
    body: "Люди — HR с Telegram, почтой, телефоном. Компании — те же люди, сгруппированные по бренду. Карточки вакансий остаются своими.",
  },
  "contacts.view": {
    title: "Люди и компании",
    body: "Люди — один контакт и все его вакансии. Компании — бренд и кто там уже есть.",
  },
  "contacts.search": {
    title: "Найти HR",
    body: "Имя, @username, почта, телефон, компания. «HR» справа — завести человека вручную, не из вакансии.",
  },

  "internships.header": {
    title: "Стажировки",
    body: "Каталог программ. Статус набора — ориентир по сайту компании.",
  },
  "internships.tabs": {
    title: "Стажировки и школы",
    body: "Стажировки — набор на работу. Школы — бесплатные курсы компаний; часто дают fast-track на отбор.",
  },
  "internships.filters": {
    title: "Фильтры",
    body: "«Открытые» — где набор сейчас по нашей разметке. «Мои» — программы, где вы поставили статус или заметку.",
  },
  "internships.list": {
    title: "Таблица",
    body: "Название ведёт на сайт компании. Статус и заметки сохраняются в аккаунт.",
  },

  "hackathons.header": {
    title: "Хакатоны",
    body: "Сводка хакатонов: регистрация, сроки, статусы.",
  },
  "hackathons.filters": {
    title: "Фильтры",
    body: "«Регистрация» — куда ещё можно подать заявку. «Новые» — сейчас открыты: идёт хакатон или открыта регистрация. Завершённые сюда не попадают. «Мои» — куда вы поставили статус.",
  },
  "hackathons.list": {
    title: "Лента",
    body: "Источник, даты и статусы слева. Трекер и заметки справа.",
  },

  "thesis.header": {
    title: "Тезис",
    body: "Гипотеза: этот сегмент ещё жив. HuntOS смотрит inbox и воронку, не только касания. Жив / слабо / мёртв — про рынок, не про одну карточку.",
  },
  "thesis.list": {
    title: "Список тезисов",
    body: "Клик выбирает охоту — Inbox и воронка сузятся. Точка — вердикт. Новый тезис — кнопка справа в шапке.",
  },
  "thesis.verdict": {
    title: "Вердикт",
    body: "Выборка — inbox + воронка за окно дней. «Новых за сутки» — когда карточка появилась у тебя, не когда её повесили на сайте.",
  },
  "thesis.corridor": {
    title: "Зарплатный рынок",
    body: "Вилка по скачанным вакансиям и зарплатным агрегаторам: Хабр Карьера, GetMatch, профессии hh.ru и Levels.fyi. Грейд и специальность сужают ту же смесь. Это статистика, не оффер.",
  },
  "thesis.wave": {
    title: "Волна",
    body: "Пачка из Inbox, которым пишешь разом. После «написал» карточки уходят в «жду ответа» и тезис пересчитывается.",
  },
  "thesis.name": {
    title: "Название",
    body: "Как охота будет называться в меню слева. Коротко: роль, формат, вилка — чтобы не путать тезисы.",
  },
  "thesis.query": {
    title: "Запрос",
    body: "Слова из роли, компании или описания. По ним тезис находит карточки в inbox. Пусто — все неисключённые вакансии.",
  },
  "thesis.grades": {
    title: "Грейд",
    body: "Ограничивает выборку тезиса. Пусто — любой грейд. Это не фильтр поиска на площадке, а правило охоты.",
  },
  "thesis.formats": {
    title: "Формат",
    body: "Удалёнка, офис, гибрид — как в карточке. Пусто — любой формат.",
  },
  "thesis.salary": {
    title: "Мин. зп",
    body: "Карточки ниже этой вилки не входят в тезис. Если зарплата скрыта, карточка тоже не пройдёт порог.",
  },
  "thesis.days": {
    title: "Ждать, дни",
    body: "Окно выборки. Раньше срока тезис редко хоронит сегмент: мало вакансий ещё не значит «мёртв».",
  },
  "thesis.min_sample": {
    title: "Мин. вакансий",
    body: "Сколько карточек нужно, чтобы вообще судить. Пока меньше — вердикт «слабо», если окно ещё идёт.",
  },
  "thesis.match": {
    title: "Мин. совпадение",
    body: "Медианный Fit с резюме. Если типичная вакансия ниже порога — сегмент не твой, даже если inbox полный.",
  },
  "thesis.exclude": {
    title: "Кроме компаний",
    body: "Яндекс, Yandex и «Яндекс.Такси» — одно имя. Enter или запятая. Такие карточки не входят в тезис и в inbox охоты.",
  },

  "settings.tabs": {
    title: "Настройки",
    body: "Профиль — резюме для Fit. Поля охоты — свои колонки на карточке. Поиски — что качать.",
  },
  "settings.resume": {
    title: "Резюме",
    body: "По нему считается Fit в Inbox. Вставь текст или загрузи PDF/TXT.",
  },
  "settings.fields": {
    title: "Поля охоты",
    body: "Чекбоксы, даты, числа на карточке этой охоты. Не путать с фильтрами поиска: это твои пометки по сделке.",
  },
  "settings.calendar": {
    title: "Календарь",
    body: "Собесы и дедлайны в календаре HuntOS.",
  },
  "settings.notify": {
    title: "Уведомления",
    body: "Свой Telegram. Раз в сутки — новые вакансии, стажировки, хакатоны. Перед собесом — коротко. Если эйчар молчит 5 дней — пинг с @алиасом.",
  },
  "settings.telegram": {
    title: "Telegram",
    body: "Каналы вакансий.",
  },
  "settings.people": {
    title: "Люди",
    body: "Кому можно смотреть чужие аккаунты. Общий пул контактов — кнопка «все» в Контактах.",
  },

  "searches.list": {
    title: "Поиски",
    body: "Сколько угодно подписок. Очередь качает площадки с паузой. Выдача попадает в inbox.",
  },
  "searches.run": {
    title: "Обновить",
    body: "Ручной прогон без ожидания кэша, встаёт в ту же очередь. Выключатель не удаляет поиск — только перестаёт качать. Карточки в inbox остаются.",
  },
  "searches.platforms": {
    title: "Площадки",
    body: "Агрегаторы — основной канал, они включены сразу. Сайты компаний — отдельный список с поиском, по умолчанию выключены. Не жми «все сайты», если не хочешь N прогонов в очередь.",
  },
  "searches.query": {
    title: "Что ищем",
    body: "Общий запрос раскладывается в фильтры каждой площадки. Пусто — площадка отдаёт свою IT-ленту, локальный стек всё равно отсеет.",
  },
  "searches.stack": {
    title: "Стек",
    body: "Языки и роли с самих площадок, не выдуманный список. На сайте компании HuntOS ещё и собирает написания: ML-инженер и ML инженер — одно.",
  },
  "searches.format": {
    title: "Формат",
    body: "Как на площадке. Где фильтра нет, HuntOS отсекает уже скачанную выдачу.",
  },
  "searches.grade": {
    title: "Грейд",
    body: "Junior…principal — как в фильтре площадки. Если у сайта нет грейда, карточка всё равно придёт, локальный стек её не выкинет только из-за этого.",
  },
  "searches.paid": {
    title: "Только с зарплатой",
    body: "Прячет вилки-секреты. Площадка без такого фильтра отдаст всё, HuntOS спрячет при копировании в inbox.",
  },
  "searches.city": {
    title: "Где",
    body: "По умолчанию вся Россия. Город снимает Россию: смотрим уже не страну, а точку. Россия снимает города. Удалёнка — в формате, не здесь.",
  },
  "searches.salary": {
    title: "Зарплата",
    body: "Порог «от» плюс своя сумма. Площадка без фильтра по деньгам отдаст всё, HuntOS отрежет при копировании в inbox.",
  },
  "searches.interval": {
    title: "Как часто",
    body: "Как часто машина сама перезапускает поиск. Между прогонами может сработать общий кэш площадки — «Обновить» его обходит.",
  },

  "card.vacancy": {
    title: "Вакансия",
    body: "Текст и скиллы. Fit считается по резюме из профиля. «Полностью» раскрывает описание, чтобы не скроллить всю карточку сразу.",
  },
  "card.stage": {
    title: "Стадия",
    body: "Стрелки двигают по воронке. Шаг «скрининг» сразу уносит из Inbox в скрининг, «собес» — в тех. собес. «тех задание» — дедлайн, колонку сам не двигает. Отказ — отдельная кнопка.",
  },
  "card.contact": {
    title: "Контакт",
    body: "Telegram, почта, телефон. Если в этой компании уже был HR — HuntOS предложит подставить. Пул всех людей — раздел Контакты.",
  },
  "card.ping": {
    title: "Пинг",
    body: "Нажми «Пинганул», когда написал ещё раз. Таймер сбросится.",
  },
  "card.hunts": {
    title: "Охоты на карточке",
    body: "Подсветить карточку в тезисе вручную. «· тезис» — она и так подходит по запросу охоты, снимать нельзя.",
  },
  "card.notes": {
    title: "Заметки",
    body: "Заметки по карточке: дедлайн теста, впечатление, о чём договорились. В поиске Inbox не участвуют.",
  },
};

export type TourStep = {
  id: string;
  href?: string;
};

/** First visit: map of HuntOS, then it switches pages. Keep this short. */
export const FIRST_TOUR: TourStep[] = [
  { id: "shell.nav", href: "/" },
  { id: "shell.hunt", href: "/" },
  { id: "inbox.header", href: "/" },
  { id: "shell.guide", href: "/" },
  { id: "pipeline.header", href: "/pipeline" },
  { id: "pipeline.board", href: "/pipeline" },
  { id: "settings.tabs", href: "/settings" },
  { id: "shell.guide", href: "/settings" },
];

export const PAGE_TITLES: Record<string, string> = {
  "/": "Inbox",
  "/pipeline": "Воронка",
  "/time": "Время",
  "/contacts": "Контакты",
  "/internships": "Стажировки",
  "/hackathons": "Хакатоны",
  "/thesis": "Тезис",
  "/settings": "Настройки",
};

/** Detailed tour for the current screen only. Started by the page button. */
export const PAGE_TOURS: Record<string, string[]> = {
  "/": ["inbox.header", "inbox.corridor", "inbox.sort", "inbox.search", "inbox.filters", "inbox.add", "inbox.list"],
  "/pipeline": ["pipeline.header", "pipeline.search", "pipeline.mass", "pipeline.nudge", "pipeline.board"],
  "/time": ["time.header", "time.range", "time.grid"],
  "/contacts": ["contacts.header", "contacts.view", "contacts.search"],
  "/internships": ["internships.header", "internships.tabs", "internships.filters", "internships.list"],
  "/hackathons": ["hackathons.header", "hackathons.filters", "hackathons.list"],
  "/thesis": ["thesis.header", "thesis.list", "thesis.verdict", "thesis.corridor", "thesis.wave"],
  "/settings": [
    "settings.tabs",
    "settings.resume",
    "settings.fields",
    "searches.list",
    "searches.platforms",
    "settings.calendar",
    "settings.notify",
    "settings.telegram",
    "settings.people",
  ],
};

const STORAGE = "hunt.guide.v3";
const PENDING_FIRST = "hunt.guide.pendingFirst";

type UserGuideState = {
  firstDone: boolean;
  muted: boolean;
};

type GuideStorage = {
  users: Record<string, UserGuideState>;
};

function emptyState(): UserGuideState {
  return { firstDone: false, muted: false };
}

function readStorage(): GuideStorage {
  try {
    const raw = localStorage.getItem(STORAGE);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<GuideStorage>;
      if (parsed.users && typeof parsed.users === "object") {
        return { users: parsed.users };
      }
    }
  } catch {
    /* empty */
  }
  return { users: {} };
}

function writeStorage(storage: GuideStorage) {
  localStorage.setItem(STORAGE, JSON.stringify(storage));
}

function readUserState(userId: number): UserGuideState {
  const row = readStorage().users[String(userId)];
  if (row) {
    return { firstDone: Boolean(row.firstDone), muted: Boolean(row.muted) };
  }
  return emptyState();
}

function writeUserState(userId: number, patch: Partial<UserGuideState>) {
  const storage = readStorage();
  const key = String(userId);
  const next = { ...readUserState(userId), ...patch };
  storage.users[key] = next;
  writeStorage(storage);
}

export function guideFirstDone(userId: number): boolean {
  return readUserState(userId).firstDone;
}

export function markGuideFirstDone(userId: number) {
  writeUserState(userId, { firstDone: true });
}

export function guideMuted(userId: number): boolean {
  return readUserState(userId).muted;
}

export function setGuideMuted(userId: number, muted: boolean) {
  writeUserState(userId, { muted, firstDone: muted ? true : readUserState(userId).firstDone });
}

/** Set after register — first tour auto-starts once for this account. */
export function setPendingFirstTour(userId: number) {
  sessionStorage.setItem(PENDING_FIRST, String(userId));
}

export function clearPendingFirstTour() {
  sessionStorage.removeItem(PENDING_FIRST);
}

export function pendingFirstTourUserId(): number | null {
  try {
    const raw = sessionStorage.getItem(PENDING_FIRST);
    if (!raw) return null;
    const id = Number(raw);
    return Number.isFinite(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}

export function shouldAutoStartFirstTour(userId: number): boolean {
  if (pendingFirstTourUserId() !== userId) return false;
  if (guideMuted(userId) || guideFirstDone(userId)) return false;
  return true;
}

export function pageTourIds(pathname: string): string[] {
  return PAGE_TOURS[pathname] || [];
}

export function pageTourTitle(pathname: string): string {
  return PAGE_TITLES[pathname] || "этой страницы";
}

export function pageTourSteps(pathname: string): TourStep[] {
  return pageTourIds(pathname).map((id) => ({ id }));
}
