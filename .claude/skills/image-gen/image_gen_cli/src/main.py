"""Image Generation CLI - AI image generation powered by OpenAI GPT Image."""

import base64
import os
import sys
from datetime import datetime
from pathlib import Path

import click
from openai import OpenAI


def get_api_key() -> str | None:
    """Get API key from environment or .env file."""
    if key := os.environ.get("OPENAI_API_KEY"):
        return key

    current = Path.cwd()
    for _ in range(10):
        env_file = current / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() == "OPENAI_API_KEY":
                    value = v.strip().strip('"').strip("'")
                    if value:
                        return value
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def get_client() -> OpenAI:
    """Get authenticated OpenAI client."""
    api_key = get_api_key()
    if not api_key:
        click.echo("Error: OPENAI_API_KEY not found", err=True)
        click.echo("Add to .env: OPENAI_API_KEY=sk-...", err=True)
        sys.exit(1)
    return OpenAI(api_key=api_key)


def generate_filename(format: str) -> str:
    """Generate a timestamped filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"image_{timestamp}.{format}"


@click.group()
def cli():
    """Image Generation CLI - Create images with OpenAI GPT Image."""
    pass


@cli.command()
@click.argument("prompt")
@click.option(
    "-o", "--output",
    help="Output file path. Auto-generated if not specified."
)
@click.option(
    "-s", "--size",
    type=click.Choice(["1024x1024", "1536x1024", "1024x1536", "auto"]),
    default="1024x1024",
    help="Image size (default: 1024x1024)"
)
@click.option(
    "-q", "--quality",
    type=click.Choice(["low", "medium", "high", "auto"]),
    default="auto",
    help="Image quality (default: auto)"
)
@click.option(
    "-f", "--format",
    "output_format",
    type=click.Choice(["png", "jpeg", "webp"]),
    default="png",
    help="Output format (default: png)"
)
@click.option(
    "-b", "--background",
    type=click.Choice(["opaque", "transparent", "auto"]),
    default="auto",
    help="Background type (default: auto). Transparent only works with png/webp."
)
@click.option(
    "-c", "--compression",
    type=click.IntRange(0, 100),
    default=None,
    help="Compression level 0-100 for jpeg/webp (default: none)"
)
@click.option(
    "-n", "--count",
    type=click.IntRange(1, 10),
    default=1,
    help="Number of images to generate (default: 1)"
)
@click.option(
    "-m", "--model",
    type=click.Choice(["gpt-image-1", "dall-e-3", "dall-e-2"]),
    default="gpt-image-1",
    help="Model to use (default: gpt-image-1)"
)
def generate(
    prompt: str,
    output: str | None,
    size: str,
    quality: str,
    output_format: str,
    background: str,
    compression: int | None,
    count: int,
    model: str,
):
    """
    Generate an image from a text prompt.

    \b
    EXAMPLES
    --------
    uv run img generate "a cat wearing a top hat"
    uv run img generate "sunset over mountains" -o sunset.png
    uv run img generate "product photo of sneakers" -s 1536x1024 -q high
    uv run img generate "app icon" -b transparent -f png
    uv run img generate "logo design" -n 3 -o logo.png
    uv run img generate "watercolor painting" -f jpeg -c 85

    \b
    SIZES
    -----
    1024x1024  Square (default, fastest)
    1536x1024  Landscape
    1024x1536  Portrait
    auto       Let model decide

    \b
    QUALITY & COST
    --------------
    low     Fastest, cheapest (~$0.01/image)
    medium  Balanced (~$0.03-0.05/image)
    high    Best quality (~$0.13-0.20/image)
    auto    Model decides (default)
    """
    client = get_client()

    # Build request parameters
    params = {
        "model": model,
        "prompt": prompt,
        "n": count,
    }

    # Size (skip 'auto' for API)
    if size != "auto":
        params["size"] = size

    # Model-specific parameters
    if model.startswith("gpt-image"):
        # GPT Image model parameters
        if quality != "auto":
            params["quality"] = quality
        if background != "auto":
            params["background"] = background
        if output_format != "png":
            params["output_format"] = output_format
        if compression is not None and output_format in ("jpeg", "webp"):
            params["output_compression"] = compression
    else:
        # DALL-E model parameters
        params["response_format"] = "b64_json"
        if model == "dall-e-3" and quality == "high":
            params["quality"] = "hd"
        elif quality in ("low", "medium"):
            params["quality"] = "standard"

    try:
        click.echo(f"Generating {count} image(s)...", err=True)
        result = client.images.generate(**params)

        for i, image_data in enumerate(result.data):
            # Determine output path
            if output:
                if count > 1:
                    # Add index for multiple images
                    base, ext = os.path.splitext(output)
                    if not ext:
                        ext = f".{output_format}"
                    filepath = f"{base}_{i+1}{ext}"
                else:
                    filepath = output
                    if not os.path.splitext(filepath)[1]:
                        filepath = f"{filepath}.{output_format}"
            else:
                if count > 1:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filepath = f"image_{timestamp}_{i+1}.{output_format}"
                else:
                    filepath = generate_filename(output_format)

            # Decode and save
            image_bytes = base64.b64decode(image_data.b64_json)
            with open(filepath, "wb") as f:
                f.write(image_bytes)

            click.echo(f"Saved: {filepath}")

            # Show revised prompt if available
            if hasattr(image_data, "revised_prompt") and image_data.revised_prompt:
                click.echo(f"Revised prompt: {image_data.revised_prompt}", err=True)

    except Exception as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower():
            click.echo("Error: Rate limit exceeded. Wait and retry.", err=True)
        elif "content_policy" in error_msg.lower():
            click.echo("Error: Prompt rejected by content policy.", err=True)
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def models():
    """
    List available image generation models.

    \b
    MODELS
    ------
    gpt-image-1   Latest GPT Image model (recommended)
                  - Best quality and instruction following
                  - Supports transparency, all sizes
                  - Text rendering, detailed editing

    dall-e-3      DALL-E 3 (deprecated May 2026)
                  - Higher quality than DALL-E 2
                  - Generation only, no editing

    dall-e-2      DALL-E 2 (deprecated May 2026)
                  - Lower cost, faster
                  - Supports variations and inpainting
    """
    click.echo("Available models:")
    click.echo()
    click.echo("  gpt-image-1  - GPT Image (recommended)")
    click.echo("  dall-e-3     - DALL-E 3 (deprecated May 2026)")
    click.echo("  dall-e-2     - DALL-E 2 (deprecated May 2026)")
    click.echo()
    click.echo("Use: uv run img generate 'prompt' -m <model>")


def convert_to_emoji_name(filename: str) -> str:
    """Convert underscore filename to hyphen emoji name convention."""
    name = Path(filename).stem
    ext = Path(filename).suffix
    # Replace underscores with hyphens
    emoji_name = name.replace("_", "-")
    return f"{emoji_name}{ext}"


def validate_image_name(filename: str) -> bool:
    """Validate image follows naming convention (at least 2 words with underscores)."""
    name = Path(filename).stem
    parts = name.split("_")
    return len(parts) >= 2


@cli.command()
@click.argument("input_image", type=click.Path(exists=True))
@click.argument("prompt")
@click.option(
    "-o", "--output",
    help="Output file path. Overwrites input if not specified."
)
@click.option(
    "-s", "--size",
    type=click.Choice(["1024x1024", "1536x1024", "1024x1536", "auto"]),
    default="auto",
    help="Output size (default: auto, preserves aspect)"
)
@click.option(
    "-q", "--quality",
    type=click.Choice(["low", "medium", "high", "auto"]),
    default="auto",
    help="Image quality (default: auto)"
)
@click.option(
    "-m", "--model",
    type=click.Choice(["gpt-image-1", "dall-e-2"]),
    default="gpt-image-1",
    help="Model to use (default: gpt-image-1)"
)
def edit(
    input_image: str,
    prompt: str,
    output: str | None,
    size: str,
    quality: str,
    model: str,
):
    """
    Edit an existing image with a text prompt.

    Takes a source image and applies edits based on the prompt.
    Great for tweaking generated images without starting from scratch.

    \b
    EXAMPLES
    --------
    uv run img edit hero.png "make the hammer look more like Mjolnir"
    uv run img edit portrait.png "add a glowing aura" -o portrait_v2.png
    uv run img edit icon.png "change the color to blue" -q high

    \b
    TIPS
    ----
    - Be specific about what to change
    - Reference existing elements: "make THE hammer bigger"
    - Describe desired outcome: "hammer should have ornate runes"
    """
    client = get_client()
    input_path = Path(input_image)

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        # Overwrite original by default
        output_path = input_path

    try:
        click.echo(f"Editing {input_path.name}...", err=True)

        # Build request parameters - pass file handle, not bytes
        params = {
            "model": model,
            "image": open(input_path, "rb"),
            "prompt": prompt,
        }

        if size != "auto":
            params["size"] = size

        if model == "gpt-image-1" and quality != "auto":
            params["quality"] = quality

        result = client.images.edit(**params)

        # Close the file handle
        params["image"].close()

        # Save result
        image_bytes = base64.b64decode(result.data[0].b64_json)
        with open(output_path, "wb") as f:
            f.write(image_bytes)

        click.echo(f"Saved: {output_path}")

        if hasattr(result.data[0], "revised_prompt") and result.data[0].revised_prompt:
            click.echo(f"Applied: {result.data[0].revised_prompt}", err=True)

    except Exception as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower():
            click.echo("Error: Rate limit exceeded. Wait and retry.", err=True)
        elif "content_policy" in error_msg.lower():
            click.echo("Error: Prompt rejected by content policy.", err=True)
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("input_image", type=click.Path(exists=True))
@click.option(
    "-o", "--output",
    help="Output path. Auto-generated from input name if not specified."
)
@click.option(
    "-s", "--size",
    type=int,
    default=128,
    help="Emoji size in pixels (default: 128, Discord standard)"
)
@click.option(
    "--max-size",
    type=int,
    default=256,
    help="Max file size in KB (default: 256, Discord limit)"
)
@click.option(
    "-f", "--format",
    "output_format",
    type=click.Choice(["png", "gif", "webp"]),
    default=None,
    help="Output format (default: preserve original, prefer PNG for transparency)"
)
def emojify(
    input_image: str,
    output: str | None,
    size: int,
    max_size: int,
    output_format: str | None,
):
    """
    Convert an image to Discord emoji format.

    Resizes image to Discord emoji specs and applies naming convention.

    \b
    NAMING CONVENTION
    -----------------
    Source images:  word_word.png     (underscores, at least 2 words)
    Emoji output:   word-word.png     (hyphens)

    \b
    EXAMPLES
    --------
    uv run img emojify town_guard.png
    uv run img emojify my_cool_icon.png -s 64
    uv run img emojify large_image.png --max-size 128
    uv run img emojify source_art.png -o custom-name.png

    \b
    DISCORD SPECS
    -------------
    - Recommended: 128x128 pixels
    - Max file size: 256KB (static), 512KB (animated)
    - Formats: PNG, GIF, WEBP (PNG best for transparency)
    """
    from PIL import Image
    import io

    input_path = Path(input_image)

    # Validate naming convention (warn but don't block)
    if not validate_image_name(input_path.name):
        click.echo(
            f"Warning: '{input_path.name}' doesn't follow naming convention "
            "(should be word_word.ext with at least 2 words)",
            err=True
        )

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        emoji_name = convert_to_emoji_name(input_path.name)
        output_path = input_path.parent / emoji_name

    # Determine format
    if output_format:
        fmt = output_format.upper()
        if fmt == "WEBP":
            fmt = "WEBP"
        output_path = output_path.with_suffix(f".{output_format}")
    else:
        fmt = input_path.suffix.upper().lstrip(".")
        if fmt == "JPG":
            fmt = "JPEG"
        elif fmt not in ("PNG", "GIF", "WEBP"):
            fmt = "PNG"
            output_path = output_path.with_suffix(".png")

    try:
        # Open and resize image
        with Image.open(input_path) as img:
            # Preserve transparency
            if img.mode in ("RGBA", "LA", "P"):
                if fmt == "PNG" or fmt == "WEBP":
                    img = img.convert("RGBA")
                else:
                    # Can't preserve transparency in GIF well, convert
                    img = img.convert("RGBA")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize with high-quality resampling
            img_resized = img.resize((size, size), Image.Resampling.LANCZOS)

            # Save with optimization
            buffer = io.BytesIO()
            save_kwargs = {"format": fmt}

            if fmt == "PNG":
                save_kwargs["optimize"] = True
            elif fmt == "WEBP":
                save_kwargs["quality"] = 90
                save_kwargs["method"] = 6
            elif fmt == "GIF":
                save_kwargs["optimize"] = True

            img_resized.save(buffer, **save_kwargs)

            # Check file size and reduce quality if needed
            max_bytes = max_size * 1024
            quality = 90

            while buffer.tell() > max_bytes and quality > 20:
                buffer = io.BytesIO()
                if fmt == "PNG":
                    # PNG doesn't have quality, try quantizing colors
                    img_quantized = img_resized.quantize(colors=256)
                    img_quantized.save(buffer, format=fmt, optimize=True)
                    break
                elif fmt in ("WEBP", "GIF"):
                    quality -= 10
                    save_kwargs["quality"] = quality
                    img_resized.save(buffer, **save_kwargs)

            # Write final output
            with open(output_path, "wb") as f:
                f.write(buffer.getvalue())

            final_size = buffer.tell()
            click.echo(f"Saved: {output_path}")
            click.echo(f"Size: {size}x{size}px, {final_size / 1024:.1f}KB")

            if final_size > max_bytes:
                click.echo(
                    f"Warning: File size ({final_size / 1024:.1f}KB) exceeds "
                    f"target ({max_size}KB)",
                    err=True
                )

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
