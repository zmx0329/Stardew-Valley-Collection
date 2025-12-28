from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..models.common import LabelPayload, NormalizedBounds, TimePayload
from .utils import clamp, wrap_text


class ImageService:
  """Composes the final artwork (tag + time) on top of the pixel image."""

  def __init__(self) -> None:
    self.font = ImageFont.load_default()
    self._clock_assets = self._load_clock_assets()

  def compose(self, base_image_bytes: bytes, label: LabelPayload, box_bounds: NormalizedBounds | None) -> bytes:
    base = Image.open(BytesIO(base_image_bytes)).convert("RGBA")
    canvas = base.copy()

    # box_bounds reserved for future alignment between detection框 and标签
    _ = box_bounds

    self._draw_tag(canvas, label)
    self._draw_time_chip(canvas, label.time)

    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()

  def _draw_tag(self, canvas: Image.Image, label: LabelPayload) -> None:
    draw = ImageDraw.Draw(canvas)
    base_width = 320
    base_height = 210
    scale = clamp(label.tag_scale, 0.6, 2.0)
    tag_width = int(base_width * scale)
    tag_height = int(base_height * scale)

    x_center = clamp(label.tag_position.x_percent, 0.05, 0.95) * canvas.width
    y_center = clamp(label.tag_position.y_percent, 0.05, 0.95) * canvas.height
    x0 = clamp(x_center - tag_width / 2, 0, canvas.width - tag_width)
    y0 = clamp(y_center - tag_height / 2, 0, canvas.height - tag_height)
    x1 = x0 + tag_width
    y1 = y0 + tag_height

    frame_color = (196, 119, 24, 255)
    fill_color = (255, 230, 179, 240)
    divider_color = (180, 104, 16, 255)

    draw.rounded_rectangle([x0, y0, x1, y1], radius=int(12 * scale), fill=fill_color, outline=frame_color, width=3)

    padding = 12 * scale
    text_x = x0 + padding
    current_y = y0 + padding

    draw.text((text_x, current_y), label.name or "未命名物品", fill=frame_color, font=self.font)
    current_y += 18 * scale
    draw.line([(text_x, current_y), (x1 - padding, current_y)], fill=divider_color, width=1)

    current_y += 8 * scale
    draw.text((text_x, current_y), label.category or "类别", fill=(110, 58, 12, 255), font=self.font)
    current_y += 14 * scale
    draw.line([(text_x, current_y), (x1 - padding, current_y)], fill=divider_color, width=3)

    current_y += 10 * scale
    body_width = x1 - padding - text_x
    description = label.description or "在这里写下物品的故事。"
    for line in wrap_text(description, limit=int(body_width / (7 * scale))):
      draw.text((text_x, current_y), line, fill=(92, 50, 10, 255), font=self.font)
      current_y += 14 * scale

    if label.category in ("菜品", "食物"):
      current_y += 6 * scale
      energy_text = f"+{label.energy} 能量"
      health_text = f"+{label.health} 生命值"
      draw.text((text_x, current_y), energy_text, fill=(46, 102, 8, 255), font=self.font)
      draw.text((text_x + body_width * 0.5, current_y), health_text, fill=(141, 26, 26, 255), font=self.font)

  def _draw_time_chip(self, canvas: Image.Image, time: TimePayload) -> None:
    clock = self._clock_assets.get("day" if 6 <= time.hour < 18 else "night")
    if clock:
      self._draw_clock_background(canvas, time, clock)
      return

    draw = ImageDraw.Draw(canvas)
    margin = 12
    box_width = 180
    box_height = 74

    x1 = canvas.width - margin
    x0 = x1 - box_width
    y0 = margin
    y1 = y0 + box_height

    wood = (206, 162, 112, 235)
    outline = (120, 82, 44, 255)

    draw.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=wood, outline=outline, width=2)

    text_x = x0 + 12
    top_y = y0 + 10
    draw.text((text_x, top_y), f"{time.month}月{time.day}日", fill=(64, 38, 12, 255), font=self.font)
    draw.text((text_x, top_y + 18), f"{time.hour:02d}:{time.minute:02d}", fill=(64, 38, 12, 255), font=self.font)

  def _load_clock_assets(self) -> dict[str, Image.Image]:
    root = Path(__file__).resolve().parents[3]
    day_path = root / "frontend" / "public" / "白天时钟.png"
    night_path = root / "frontend" / "public" / "夜晚时钟.png"
    assets: dict[str, Image.Image] = {}
    try:
      assets["day"] = Image.open(day_path).convert("RGBA")
      assets["night"] = Image.open(night_path).convert("RGBA")
    except Exception:
      return {}
    return assets

  def _draw_clock_background(self, canvas: Image.Image, time: TimePayload, clock: Image.Image) -> None:
    draw = ImageDraw.Draw(canvas)
    margin = 12
    clock_width = 200
    scale = clock_width / clock.width
    clock_height = int(clock.height * scale)

    x1 = canvas.width - margin
    x0 = x1 - clock_width
    y0 = margin

    resized = clock.resize((clock_width, clock_height), resample=Image.NEAREST)
    canvas.alpha_composite(resized, (int(x0), int(y0)))

    date_label = self._format_date_label(time)
    time_label = f"{time.hour:02d}:{time.minute:02d}"

    date_left = x0 + clock_width * 0.38
    date_center_x = date_left + clock_width * 0.54 / 2
    date_center_y = y0 + clock_height * 0.199

    time_left = x0 + clock_width * 0.38
    time_center_x = time_left + clock_width * 0.54 / 2
    time_center_y = y0 + clock_height * 0.535

    text_color = (58, 36, 22, 255)
    draw.text((date_center_x, date_center_y), date_label, fill=text_color, font=self.font, anchor="mm")
    draw.text((time_center_x, time_center_y), time_label, fill=text_color, font=self.font, anchor="mm")

  def _format_date_label(self, time: TimePayload) -> str:
    year = date.today().year
    try:
      weekday = date(year, time.month, time.day).weekday()
    except ValueError:
      weekday = 0
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return f"{time.day}日 {weekdays[weekday]}"
