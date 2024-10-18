import os
import re
import requests
from PIL import Image
from io import BytesIO
from datetime import datetime

def download_and_convert_image(url, output_path):
    response = requests.get(url)
    if response.status_code == 200:
        image = Image.open(BytesIO(response.content))
        # Convert the image to PNG and save it
        image.save(output_path, 'PNG')
        print(f"Image saved as {output_path}")
    else:
        print(f"Failed to download image from {url}")

def update_md_with_local_paths(md_content, base_url, local_dir, date_str, md_filename):
    # Define a pattern to match the webp image URLs
    pattern = r'\!\[.*?\]\((https://cdn\.nlark\.com/.*?\.webp)\)'
    matches = re.findall(pattern, md_content)

    for i, match in enumerate(matches):
        # Create a new filename for the converted image
        img_name = f'img_{i}.png' if i > 0 else 'img.png'
        local_img_path = os.path.join(local_dir, img_name)

        # Download and convert the image
        download_and_convert_image(match, local_img_path)

        # Construct the new URL for the image
        new_url = f'{base_url}{date_str}-{md_filename}/{img_name}'

        # Replace the old URL with the new one in the markdown content
        md_content = md_content.replace(match, new_url)

    return md_content

def main(md_file_path):
    # Read the markdown file
    with open(md_file_path, 'r', encoding='utf-8') as file:
        md_content = file.read()

    # Get the current date and MD filename
    date_str = datetime.now().strftime('%Y-%m-%d')
    md_filename = os.path.splitext(os.path.basename(md_file_path))[0]

    # Define the local directory for images
    local_dir = f'/Users/xyhao/workspace/Blog/assets/articleSource/{date_str}-{md_filename}'
    os.makedirs(local_dir, exist_ok=True)

    # Base URL for the GitHub repository
    base_url = 'https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/'

    # Update the markdown content with the local paths
    updated_content = update_md_with_local_paths(md_content, base_url, local_dir, date_str, md_filename)

    # Write the updated markdown back to the file
    with open(md_file_path, 'w', encoding='utf-8') as file:
        file.write(updated_content)
    print("Markdown file has been updated.")

if __name__ == '__main__':
    # Provide the path to your Markdown file here
    md_file_path = '如何优雅地重试.md'
    main(md_file_path)