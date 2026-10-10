from pathlib import Path
from openpyxl import Workbook

target = Path(__file__).parent / "fixtures" / "demo.xlsx"
target.parent.mkdir(parents=True, exist_ok=True)

wb = Workbook()
ws = wb.active
ws.title = "ТЗ"
ws.append(["Параметр", "Значение"])
ws.append(["Общая площадь объекта", "1200 м²"])
ws.append(["График уборки", "5/2"])
ws.append(["Отсрочка оплаты", "30 календарных дней"])
wb.save(target)
print(target)
