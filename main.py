"""
EnglishCard - Приложение для изучения английского языка
"""

import streamlit as st
import psycopg2
import pandas as pd
import random

# ============================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================
st.set_page_config(
    page_title="EnglishCard - Изучение английского",
    page_icon="📚",
    layout="wide"
)


# ============================================================
# РАБОТА С БАЗОЙ ДАННЫХ
# ============================================================

def get_db_connection():
    """
    TODO: Реализовать подключение к PostgreSQL
    Параметры подключения:
    - host: localhost
    - database: english_card
    - user: postgres
    - password: postgres
    """

    return psycopg2.connect(
        host="localhost",
        database="english_card",
        user="postgres",
        password="postgres"
    )


def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Таблица общих слов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS common_words (
                id SERIAL PRIMARY KEY,
                russian_word VARCHAR(100) NOT NULL,
                english_word VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (russian_word, english_word)
            )
        """)

        # 3. Таблица персональных слов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_words (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                russian_word VARCHAR(100) NOT NULL,
                english_word VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Таблица статистики
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_stats (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                word_id INTEGER NOT NULL,
                word_type VARCHAR(20) NOT NULL,
                correct_answers INTEGER DEFAULT 0,
                total_attempts INTEGER DEFAULT 0,
                last_reviewed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, word_id, word_type)
            )
        """)

        # Заполнение 10 базовыми словами
        initial_words = [
            ('красный', 'red'), ('синий', 'blue'), ('зеленый', 'green'),
            ('я', 'I'), ('ты', 'you'), ('он', 'he'),
            ('кот', 'cat'), ('собака', 'dog'), ('дом', 'house'), ('вода', 'water')
        ]

        for ru, en in initial_words:
            cursor.execute("""
                INSERT INTO common_words (russian_word, english_word) 
                VALUES (%s, %s) 
                ON CONFLICT (russian_word, english_word) DO NOTHING
            """, (ru, en))

        conn.commit()
        st.success("База данных инициализирована (10 базовых слов)")

    except psycopg2.Error as e:
        st.error(f"Ошибка инициализации БД: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def login_user(username: str) -> int | None:
    """
    Реализует вход пользователя.
    Если пользователь существует - возвращает его id.
    Если нет - создает нового и возвращает его id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()

        if result:
            return result[0]  # Пользователь существует, возвращаем ID

        # Создаем нового пользователя
        cursor.execute("INSERT INTO users (username) VALUES (%s) RETURNING id", (username,))
        conn.commit()
        return cursor.fetchone()[0]
    except psycopg2.Error as e:
        st.error(f"Ошибка базы данных при входе: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def get_user_words(user_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT id, russian_word, english_word, 'common' AS word_type 
            FROM common_words
            UNION ALL
            SELECT id, russian_word, english_word, 'personal' AS word_type 
            FROM user_words 
            WHERE user_id = %s
            ORDER BY word_type DESC, id ASC
        """
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "russian_word": row[1],
                "english_word": row[2],
                "word_type": row[3]
            }
            for row in rows
        ]
    except psycopg2.Error as e:
        st.error(f"Ошибка базы данных при получении слов: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def add_personal_word(user_id: int, russian_word: str, english_word: str) -> bool:
    """
    Добавляет персональное слово для пользователя.
    Проверяет на дубликаты. Возвращает True/False.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 1 FROM user_words 
            WHERE user_id = %s 
              AND LOWER(russian_word) = LOWER(%s) 
              AND LOWER(english_word) = LOWER(%s)
        """, (user_id, russian_word, english_word))

        if cursor.fetchone():
            return False  # Слово уже существует

        # Добавляем новое слово
        cursor.execute("""
            INSERT INTO user_words (user_id, russian_word, english_word) 
            VALUES (%s, %s, %s)
        """, (user_id, russian_word, english_word))
        conn.commit()
        return True
    except psycopg2.Error as e:
        st.error(f"Ошибка базы данных при добавлении слова: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def delete_personal_word(user_id: int, word_id: int) -> bool:
    """
    Удаляет персональное слово пользователя.
    Обязательно проверяет user_id для безопасности.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM user_words 
            WHERE id = %s AND user_id = %s
        """, (word_id, user_id))
        conn.commit()

        # покажет количество удаленных строк (1 или 0)
        return cursor.rowcount > 0
    except psycopg2.Error as e:
        st.error(f"Ошибка базы данных при удалении слова: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def update_stats(user_id: int, word_id: int, word_type: str, is_correct: bool) -> None:
    """
    Обновляет статистику изучения слова.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        correct_increment = 1 if is_correct else 0

        cursor.execute("""
            INSERT INTO learning_stats (user_id, word_id, word_type, correct_answers, total_attempts, last_reviewed)
            VALUES (%s, %s, %s, %s, 1, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, word_id, word_type) 
            DO UPDATE SET 
                correct_answers = learning_stats.correct_answers + %s,
                total_attempts = learning_stats.total_attempts + 1,
                last_reviewed = CURRENT_TIMESTAMP
        """, (user_id, word_id, word_type, correct_increment, correct_increment))
        conn.commit()
    except psycopg2.Error as e:
        st.error(f"Ошибка базы данных при обновлении статистики: {e}")
    finally:
        cursor.close()
        conn.close()


def get_statistics(user_id: int) -> dict:
    """
    Получает агрегированную статистику пользователя.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT word_id) as unique_words,
                COALESCE(SUM(total_attempts), 0) as total_attempts,
                COALESCE(SUM(correct_answers), 0) as correct_answers
            FROM learning_stats
            WHERE user_id = %s
        """, (user_id,))
        row = cursor.fetchone()

        unique_words = row[0] or 0
        total_attempts = row[1] or 0
        correct_answers = row[2] or 0

        # Расчет точности (защита от деления на ноль)
        accuracy = (correct_answers / total_attempts * 100) if total_attempts > 0 else 0.0

        return {
            "unique_words": unique_words,
            "total_attempts": total_attempts,
            "correct_answers": correct_answers,
            "accuracy": round(accuracy, 1)
        }
    except psycopg2.Error as e:
        st.error(f"Ошибка базы данных при получении статистики: {e}")
        return {"unique_words": 0, "total_attempts": 0, "correct_answers": 0, "accuracy": 0.0}
    finally:
        cursor.close()
        conn.close()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def generate_options(correct_word: str, all_words: list) -> list:
    """
    Генерирует 4 варианта ответа для викторины.
    """
    # Получаем все уникальные английские слова, кроме правильного
    other_words = list(set([
        w['english_word'] for w in all_words
        if w['english_word'].lower() != correct_word.lower()
    ]))

    # Запасные слова, если в словаре пользователя слишком мало слов (< 4)
    dummy_words = ["apple", "banana", "orange", "table", "chair", "window", "door", "book", "car", "tree"]

    while len(other_words) < 3:
        for dw in dummy_words:
            if dw.lower() != correct_word.lower() and dw not in other_words:
                other_words.append(dw)
            if len(other_words) == 3:
                break

    # Случайно выбираем 3 неправильных варианта
    wrong_options = random.sample(other_words, 3)

    # Объединяем с правильным ответом и перемешиваем
    options = wrong_options + [correct_word.strip()]
    random.shuffle(options)

    return options


# ============================================================
# ИНТЕРФЕЙС ПРИЛОЖЕНИЯ
# ============================================================

def render_sidebar():
    """
    Реализует боковую панель с авторизацией.
    """
    with st.sidebar:
        st.title("Профиль")

        # Если пользователь уже вошел
        if st.session_state.get("user_id"):
            st.success(f"Вы вошли как: **{st.session_state.username}**")
            st.divider()
            st.write(f"ID пользователя: {st.session_state.user_id}")

            if st.button("Выйти", use_container_width=True):
                # Сброс состояния сессии при выходе
                st.session_state.user_id = None
                st.session_state.username = ""
                st.session_state.current_word_idx = 0
                st.rerun()
        else:
            # Форма входа для новых пользователей
            st.info("Введите имя для входа в систему")
            username = st.text_input("Ваше имя:", placeholder="Например: Ivan")

            if st.button("Войти", use_container_width=True, type="primary"):
                if username.strip():
                    user_id = login_user(username.strip())
                    if user_id:
                        st.session_state.user_id = user_id
                        st.session_state.username = username.strip()
                        st.session_state.current_word_idx = 0
                        st.rerun()
                    else:
                        st.error("Ошибка входа. Попробуйте снова.")
                else:
                    st.warning("Пожалуйста, введите имя!")

        st.divider()
        st.caption("EnglishCard v1.0\nКурсовая работа по БД")


def render_study_tab(words: list):
    st.subheader("Проверь свои знания")

    if not words:
        st.warning("В вашем словаре нет слов. Добавьте их во вкладке 'Добавить слово'!")
        return

    # Проверка выхода за границы
    if st.session_state.current_word_idx >= len(words):
        st.success("Поздравляем! Вы прошли все слова в словаре!")
        if st.button("Начать сначала", key="restart_quiz_btn"):
            st.session_state.current_word_idx = 0
            st.session_state.quiz_result = None
            st.session_state.current_options = []
            st.session_state.selected_answer = None
            st.rerun()
        return

    current_word = words[st.session_state.current_word_idx]

    st.caption(f"Слово {st.session_state.current_word_idx + 1} из {len(words)}")
    st.markdown(f"### Как переводится слово: **{current_word['russian_word']}**?")

    # Генерируем варианты, если их ещё нет
    if not st.session_state.get("current_options") or len(st.session_state.current_options) != 4:
        st.session_state.current_options = generate_options(current_word["english_word"], words)

    options = st.session_state.current_options

    # Проверка ответа
    def check_answer(selected_option):
        if selected_option.strip().lower() == current_word["english_word"].strip().lower():
            st.session_state.quiz_result = "correct"
            update_stats(st.session_state.user_id, current_word["id"], current_word["word_type"], True)
        else:
            st.session_state.quiz_result = "wrong"
            update_stats(st.session_state.user_id, current_word["id"], current_word["word_type"], False)
        st.session_state.selected_answer = selected_option

    # Отображаем кнопки вариантов
    cols = st.columns(2)
    for i, option in enumerate(options):
        with cols[i % 2]:
            btn_key = f"opt_idx{st.session_state.current_word_idx}_word{current_word['id']}_{i}"
            disabled = st.session_state.get("quiz_result") is not None

            st.button(
                option,
                key=btn_key,
                use_container_width=True,
                disabled=disabled,
                on_click=check_answer,
                args=(option,)
            )

    # Показываем результат
    if st.session_state.get("quiz_result") == "correct":
        st.success(f"Верно! Правильный ответ: **{current_word['english_word']}**")
    elif st.session_state.get("quiz_result") == "wrong":
        st.error(f"Неверно. Правильный ответ: **{current_word['english_word']}**")

    # Кнопки навигации
    if st.session_state.get("quiz_result") is not None:
        st.divider()
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            if st.button("Предыдущее", key="btn_prev", disabled=(st.session_state.current_word_idx == 0),
                         use_container_width=True):
                st.session_state.current_word_idx -= 1
                st.session_state.quiz_result = None
                st.session_state.current_options = []
                st.session_state.selected_answer = None
                st.rerun()

        with col2:
            if st.button("Сброс", key="btn_reset", use_container_width=True):
                st.session_state.current_word_idx = 0
                st.session_state.quiz_result = None
                st.session_state.current_options = []
                st.session_state.selected_answer = None
                st.rerun()

        with col3:
            if st.button("Следующее", key="btn_next", disabled=(st.session_state.current_word_idx >= len(words) - 1),
                         use_container_width=True, type="primary"):
                st.session_state.current_word_idx += 1
                st.session_state.quiz_result = None
                st.session_state.current_options = []
                st.session_state.selected_answer = None
                st.rerun()

        st.progress((st.session_state.current_word_idx + 1) / len(words))
    else:
        st.info("Выберите вариант ответа выше")


def render_add_word_tab():
    """
    Реализует вкладку добавления нового слова.
    """
    st.subheader("Добавить новое слово")

    with st.form("add_word_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            russian_word = st.text_input("Слово на русском:", placeholder="Например: яблоко")
        with col2:
            english_word = st.text_input("Перевод на английский:", placeholder="Например: apple")

        submitted = st.form_submit_button("Добавить слово", use_container_width=True, type="primary")

        if submitted:
            if russian_word.strip() and english_word.strip():
                success = add_personal_word(
                    st.session_state.user_id,
                    russian_word.strip(),
                    english_word.strip()
                )
                if success:
                    st.success(f"Слово '{russian_word}' добавлено в ваш словарь!")
                    # Показываем общее количество слов
                    words = get_user_words(st.session_state.user_id)
                    st.info(f"Всего в вашем словаре: **{len(words)}** слов")
                else:
                    st.warning(f"Такое слово уже есть в вашем словаре!")
            else:
                st.error("Заполните оба поля!")

    # Подсказка
    st.info("Добавленные слова появятся в викторине сразу после добавления.")


def render_delete_word_tab(words: list):
    """
    Реализует вкладку удаления персональных слов.
    """
    st.subheader("Удалить слово")

    # Фильтруем только персональные слова пользователя
    personal_words = [w for w in words if w["word_type"] == "personal"]

    if not personal_words:
        st.info("У вас нет персональных слов для удаления.")
        return

    # Создаем словарь для маппинга: "русское - английское" -> id
    word_options = {f"{w['russian_word']} — {w['english_word']}": w["id"] for w in personal_words}

    selected_word = st.selectbox(
        "Выберите слово для удаления:",
        options=list(word_options.keys()),
        index=0
    )

    if st.button("Удалить выбранное слово", type="primary", use_container_width=True):
        word_id = word_options[selected_word]
        success = delete_personal_word(st.session_state.user_id, word_id)
        if success:
            st.success(f"Слово '{selected_word}' удалено!")
            st.rerun()
        else:
            st.error("Ошибка при удалении слова.")

    # Предупреждение
    st.warning("Удаление персонально только для вас. Общие слова удалить нельзя.")


def render_statistics_tab(user_id: int):
    """
    Реализует вкладку статистики изучения (дополнительное требование).
    """
    st.subheader("Ваша статистика")

    stats = get_statistics(user_id)

    # Отображение метрик в колонках
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="Слов изучено", value=stats["unique_words"])
    with col2:
        st.metric(label="Всего попыток", value=stats["total_attempts"])
    with col3:
        st.metric(label="Правильных ответов", value=stats["correct_answers"])
    with col4:
        st.metric(label="Точность", value=f"{stats['accuracy']}%")

    st.divider()

    # Визуализация прогресса
    if stats["total_attempts"] > 0:
        st.progress(stats["accuracy"] / 100)
        st.caption(f"Ваша текущая точность: {stats['accuracy']}%")
    else:
        st.info("Пройдите викторину, чтобы увидеть статистику!")

    # Рекомендации
    if stats["accuracy"] < 50 and stats["total_attempts"] > 0:
        st.warning("Совет: Попробуйте повторить сложные слова еще раз!")
    elif stats["accuracy"] >= 80:
        st.success("Отличный результат! Продолжайте в том же духе!")


def render_schema():
    """
    Реализует отображение схемы базы данных (дополнительное требование).
    """
    st.subheader("Схема базы данных")

    schema_description = """
    ### Таблицы базы данных `english_card`

    | Таблица | Описание |
    |---------|----------|
    | **users** | Хранит информацию о пользователях (id, username, created_at) |
    | **common_words** | Общий словарь слов для всех пользователей (id, russian_word, english_word) |
    | **user_words** | Персональные слова пользователей (id, user_id, russian_word, english_word) |
    | **learning_stats** | Статистика изучения слов (id, user_id, word_id, correct_answers, total_attempts) |

    ### Диаграмма связей (ER-диаграмма)
    ```
    users (1) ──────< (N) user_words
       │
       │
       └──────< (N) learning_stats

    common_words (1) ──────< (N) learning_stats
    ```

    ### Ключевые особенности:
    - **Безопасность**: Персональные слова привязаны к user_id (ON DELETE CASCADE)
    - **Статистика**: Уникальный ключ (user_id, word_id, word_type) предотвращает дублирование
    - **UPSERT**: Используется ON CONFLICT для атомарного обновления статистики
    """

    st.markdown(schema_description)

    # Кнопка для отображения реальной структуры из БД
    if st.button("Показать реальную структуру из БД"):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT table_name, column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                ORDER BY table_name, ordinal_position
            """)
            rows = cursor.fetchall()

            df = pd.DataFrame(rows, columns=["Таблица", "Колонка", "Тип данных"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        except psycopg2.Error as e:
            st.error(f"Ошибка при получении структуры: {e}")
        finally:
            cursor.close()
            conn.close()


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    """
    Главная функция приложения
    """
    st.set_page_config(
        page_title="EnglishCard - Изучай английский",
        page_icon="📚",
        layout="wide"
    )

    # Инициализация БД при запуске
    init_database()

    # Инициализация session_state
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "current_word_idx" not in st.session_state:
        st.session_state.current_word_idx = 0
    if "quiz_result" not in st.session_state:
        st.session_state.quiz_result = None
    if "current_options" not in st.session_state:
        st.session_state.current_options = []
    if "selected_answer" not in st.session_state:
        st.session_state.selected_answer = None
    # Боковая панель
    render_sidebar()

    # Основной контент
    if st.session_state.user_id:
        st.title(f"EnglishCard - Привет, {st.session_state.username}!")

        # Получаем слова пользователя
        words = get_user_words(st.session_state.user_id)

        # Создаем вкладки
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Изучение",
            "Добавить слово",
            "Удалить слово",
            "Статистика",
            "Схема БД"
        ])

        with tab1:
            render_study_tab(words)
        with tab2:
            render_add_word_tab()
        with tab3:
            render_delete_word_tab(words)
        with tab4:
            render_statistics_tab(st.session_state.user_id)
        with tab5:
            render_schema()
    else:
        # Приветственное сообщение для неавторизованных
        st.title("Добро пожаловать в EnglishCard!")
        st.markdown("""
        ### Это приложение поможет вам выучить английский язык!

        #### Что вы можете делать:
        -  **Проходить викторины** с выбором правильного перевода из 4 вариантов
        -  **Добавлять свои собственные слова** для персонального изучения
        -  **Удалять слова** из своего словаря (персонально для вас)
        -  **Отслеживать статистику**: точность, количество попыток, прогресс
        -  **Просматривать схему базы данных**

        ---

        ###  Как начать?
        1. Введите ваше имя в боковой панели слева
        2. Нажмите кнопку "Войти"
        3. Начните изучение слов во вкладке "Изучение"!

        ---

        *Приложение разработано в рамках курсовой работы по курсу "Базы данных"*
        """)

        # Декоративные элементы
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Слов в базе", "10+")
        with col2:
            st.metric("Режимов", "4")
        with col3:
            st.metric("Язык", "🇬🇧/🇷🇺")


if __name__ == "__main__":
    main()
