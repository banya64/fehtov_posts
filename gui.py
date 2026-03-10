import threading
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import sqlite3
import postohtml
import export_posts_local


def connect_to_db():
    global conn, cursor
    try:
        conn = sqlite3.connect('posts.db')  # Замените на свой файл базы данных
        cursor = conn.cursor()
        conn.commit()
        load_data()
    except sqlite3.Error as e:
        messagebox.showerror("Ошибка базы данных", str(e))


def load_data():
    for row in tree.get_children():
        tree.delete(row)

    try:
        cursor.execute("SELECT id, text, date FROM posts")  # Выбор ID, текста и даты
        rows = cursor.fetchall()
        sorted_data = sort_by_id(rows)
        for row in sorted_data:
        #for row in rows:
            tree.insert("", tk.END, values=row)  # Добавление ID в скрытую колонку
    except sqlite3.Error as e:
        messagebox.showerror("Ошибка загрузки данных", str(e))

def sort_by_id(data):
    return sorted(data, key=lambda x: x[0], reverse=True)

def show_details(event):
    selected_item = tree.selection()
    if selected_item:
        item_id = tree.item(selected_item[0], "value")[0]

        for widget in frame_details.winfo_children():
            widget.destroy()

        try:
            # Основная информация о посте
            cursor.execute("SELECT html FROM posts WHERE id = ?", (item_id,))
            post_data = cursor.fetchall()


            # Формирование строки для отображения
            html_frame = tk.Frame(frame_details, bg="lightblue", padx=10, pady=10, height = 300)
            html_frame.pack(fill=tk.X)
            html_frame.pack_propagate(False)
            html_code = tk.Text(html_frame, bg="lightblue", font=("Arial", 10))
            ready_text = "\n".join(", ".join(map(str, item)) if isinstance(item, (list, tuple)) else str(item) for item in post_data)
            html_code.insert("1.0", ready_text)
            html_code.config(state="disabled")
            html_code.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            scrollbar = ttk.Scrollbar(html_code, orient="vertical", command=html_code.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            html_code.config(yscrollcommand=scrollbar.set)
            copy_button = tk.Button(html_frame, text="Копировать", command=lambda: copy_to_clipboard(html_code))
            copy_button.pack(side=tk.RIGHT, pady=10)
            # Обновление текстового поля
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка загрузки деталей", str(e))

def _run_update_thread():
    """Выполняет postohtml.main() в фоне и по завершении обновляет GUI."""
    try:
        postohtml.main()
        root.after(0, _on_update_done, None)
    except Exception as e:
        root.after(0, _on_update_done, e)

def _run_export_thread():
    """Выполняет экспорт постов в фоне (без подвисания GUI)."""
    try:
        exported, skipped = export_posts_local.export_posts(only_new=True)
        root.after(0, _on_export_done, None, exported, skipped)
    except Exception as e:
        root.after(0, _on_export_done, e, 0, 0)


def _on_export_done(error, exported: int, skipped: int):
    if error is None:
        if exported > 0:
            messagebox.showinfo("Готово", f"Экспорт завершён. Новых постов: {exported}.")
        else:
            messagebox.showinfo("Готово", "Новых постов для экспорта нет.")
    else:
        messagebox.showerror("Ошибка", f"Ошибка экспорта постов: {error}")


def export_posts():
    """Старт экспорта (в фоне)."""
    threading.Thread(target=_run_export_thread, daemon=True).start()


def _on_update_done(error):
    """Вызывается в главном потоке после завершения обновления."""
    btn_run_script.config(state=tk.NORMAL)
    if error is None:
        messagebox.showinfo("Готово", "Скрипт выполнен успешно!")
        load_data()
        export_posts()

        
    else:
        messagebox.showerror("Ошибка", f"Ошибка выполнения скрипта: {error}")


def run_script_and_update():
    """Запуск скрипта в фоне и обновление таблицы по завершении."""
    btn_run_script.config(state=tk.DISABLED)
    threading.Thread(target=_run_update_thread, daemon=True).start()


def copy_to_clipboard(text_widget):
    # Получаем текст из текстового поля
    text = text_widget.get("1.0", tk.END).strip()  # Удаляем лишние пробелы и символы новой строки
    # Копируем текст в буфер обмена
    root.clipboard_clear()  # Очищаем буфер обмена
    root.clipboard_append(text)  # Добавляем текст в буфер обмена
    root.update()  # Обновляем буфер обмена

root = tk.Tk()
root.geometry("1000x800")
root.title("Fehtov")

frame_details = tk.Frame(root, padx=10, pady=10)
frame_details.pack(fill=tk.BOTH, expand=True)
detail_label = tk.Label(frame_details, text="Выберите строку для отображения деталей.", anchor="w", justify="left", bg="white", relief="solid", height=5, padx=10)
detail_label.pack(fill=tk.BOTH, expand=True)

frame_buttons = tk.Frame(root, padx=10, pady=10)
frame_buttons.pack(fill=tk.X)

# Кнопка запуска скрипта
btn_run_script = tk.Button(frame_buttons, text="Обновить таблицу", command=run_script_and_update)
btn_run_script.pack(side=tk.RIGHT)


# Верхняя панель для ввода данных
frame_table = tk.Frame(root, padx=10, pady=10)
frame_table.pack(fill=tk.BOTH, expand=True)

tree = ttk.Treeview(frame_table, columns=("id", "text", "date"), show="headings", height=10)
tree.heading("id", text="ID")  # Заголовок для ID
tree.heading("text", text="Текст поста")
tree.heading("date", text="Дата создания")
tree.column("id", width=0, stretch=tk.NO)
tree.column("text", width=150, anchor=tk.W)
tree.column("date", width=100, anchor=tk.CENTER)
tree.pack(fill=tk.BOTH, expand=True)

tree.bind("<<TreeviewSelect>>", show_details)



# Подключение к базе данных и загрузка данных
connect_to_db()


def start_app():
    root.mainloop()


if __name__ == "__main__":
    start_app()