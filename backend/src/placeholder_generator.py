import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    pass

class PlaceholderImageGenerator:
    """Generates placeholder images with descriptive text overlays."""

    COLORS = [
        ("#2C3E50", "#ECF0F1"),  # Dark blue-gray / light gray
        ("#1A5276", "#D4E6F1"),  # Navy / light blue
        ("#145A32", "#D5F5E3"),  # Dark green / light green
        ("#6C3483", "#E8DAEF"),  # Purple / light purple
        ("#922B21", "#FADBD8"),  # Dark red / light pink
        ("#1B4F72", "#AED6F1"),  # Deep blue / sky blue
    ]

    def __init__(self):
        self._color_index = 0

    def generate_image(
        self,
        description: str,
        output_path: str,
        width: int = 1600,
        height: int = 900,
    ) -> str:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        bg_color, text_color = self.COLORS[self._color_index % len(self.COLORS)]
        self._color_index += 1

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Draw border
        border = 12
        draw.rectangle(
            [border, border, width - border - 1, height - border - 1],
            outline=text_color,
            width=4,
        )

        # Draw crosshair lines (visual placeholder indicator)
        draw.line([(border, border), (width - border, height - border)],
                  fill=text_color, width=2)
        draw.line([(width - border, border), (border, height - border)],
                  fill=text_color, width=2)

        # Draw center label
        try:
            # Try to load a larger default font
            font_large = ImageFont.truetype("arial.ttf", 64)
            font_small = ImageFont.truetype("arial.ttf", 48)
        except OSError:
            font_large = ImageFont.load_default()
            font_small = font_large

        # "PLACEHOLDER IMAGE" label
        label = "PLACEHOLDER IMAGE"
        bbox = draw.textbbox((0, 0), label, font=font_large)
        lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        lx = (width - lw) // 2
        ly = height // 2 - lh - 40

        # Background box for label
        pad = 20
        draw.rectangle(
            [lx - pad, ly - pad, lx + lw + pad, ly + lh + pad],
            fill=bg_color,
        )
        draw.text((lx, ly), label, fill=text_color, font=font_large)

        # Description text (wrapped)
        wrapped = self._wrap_text(description, max_chars=60)
        desc_y = ly + lh + pad + 20
        for line in wrapped[:4]:  # max 4 lines
            bbox = draw.textbbox((0, 0), line, font=font_small)
            tw = bbox[2] - bbox[0]
            tx = (width - tw) // 2
            
            # Background for readability
            desc_pad = 8
            draw.rectangle(
                [tx - desc_pad, desc_y - desc_pad, tx + tw + desc_pad, desc_y + (bbox[3] - bbox[1]) + desc_pad],
                fill=bg_color,
            )
            draw.text((tx, desc_y), line, fill=text_color, font=font_small)
            desc_y += (bbox[3] - bbox[1]) + desc_pad * 3

        img.save(output_path, quality=95)
        return output_path

    @staticmethod
    def _wrap_text(text: str, max_chars: int = 60) -> list[str]:
        words = text.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 <= max_chars:
                current = f"{current} {word}" if current else word
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
