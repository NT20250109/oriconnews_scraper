from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse
import time
import shutil

# Flaskアプリケーションの初期化
app = Flask(__name__)

# 画像を保存するディレクトリ
STATIC_DIR = 'static'
DOWNLOAD_DIR = os.path.join(STATIC_DIR, 'downloads')

def scrape_images(target_url):
    """
    指定されたURLから高解像度の画像を抽出するロジック。
    Oricon Newsの構造に合わせて最適化されています。
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    saved_image_paths = []

    # Oricon News専用のロジック
    if "oricon.co.jp/news/" in target_url:
        print("Oricon NewsのURLを検出しました。高解像度モードで実行します。")
        try:
            # ステップ1: 記事ページから写真ページへのリンクを収集
            response = requests.get(target_url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            link_tags = soup.select('div.inner-photo a, section.block-photo-preview a')
            
            photo_page_urls = set()
            for link in link_tags:
                href = link.get('href')
                if href and 'photo' in href:
                    photo_page_urls.add(urljoin(target_url, href))
            
            # ステップ2: 各写真ページから高解像度画像を取得
            for page_url in sorted(list(photo_page_urls)):
                time.sleep(0.2)
                page_res = requests.get(page_url, headers=headers, timeout=10)
                page_soup = BeautifulSoup(page_res.text, 'html.parser')
                meta_tag = page_soup.select_one('meta[property="og:image"]')
                high_res_url = meta_tag.get('content') if meta_tag and meta_tag.get('content') and "_p_o_" in meta_tag.get('content') else None
                
                if high_res_url:
                    saved_image_paths.append(high_res_url)

        except Exception as e:
            print(f"Oricon Newsの処理中にエラーが発生: {e}")
            # エラーが発生した場合、汎用ロジックに切り替える
            print("汎用的な画像抽出モードに切り替えます。")
            return scrape_general_images(target_url) # scrape_general_imagesを呼び出す
    
    # oricon以外のサイト、またはoriconでエラーが発生した場合の汎用ロジック
    if not saved_image_paths:
         saved_image_paths = scrape_general_images(target_url)
            
    # 見つかったURLから画像をダウンロード
    downloaded_files = []
    for image_url in saved_image_paths:
        try:
            time.sleep(0.1)
            image_res = requests.get(image_url, headers=headers, stream=True, timeout=10)
            image_res.raise_for_status()

            image_name = os.path.basename(urlparse(image_url).path)
            if not image_name:
                continue

            save_path = os.path.join(DOWNLOAD_DIR, image_name)
            with open(save_path, 'wb') as f:
                for chunk in image_res.iter_content(8192):
                    f.write(chunk)
            
            # ブラウザで表示するためのパスに変換
            web_path = os.path.join('downloads', image_name).replace('\\', '/')
            downloaded_files.append(web_path)
            print(f"保存しました: {image_name}")

        except Exception as e:
            print(f"ダウンロード失敗: {image_url}, {e}")
            
    return downloaded_files


def scrape_general_images(target_url):
    """
    任意のURLからimgタグの画像を抽出する汎用ロジック
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    found_urls = []
    try:
        response = requests.get(target_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for img in soup.select('img'):
            src = img.get('data-src') or img.get('src')
            if src and not src.startswith('data:'):
                found_urls.append(urljoin(target_url, src))
    except Exception as e:
        print(f"汎用モードでの解析中にエラーが発生: {e}")

    # 画像サイズの大きい順に並び替える（簡易的な高解像度判定）
    # この処理は時間がかかる場合があるため、必要に応じてコメントアウトしてください
    def get_image_size(url):
        try:
            res = requests.head(url, headers=headers, timeout=5)
            return int(res.headers.get('content-length', 0))
        except:
            return 0
    
    # 上位20件など、数を絞ると高速化できます
    sorted_urls = sorted(found_urls, key=get_image_size, reverse=True)[:20]

    return sorted_urls


# URL '/' にアクセスしたときの処理
@app.route('/', methods=['GET', 'POST'])
def index():
    # 以前のダウンロード結果を削除
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR)

    if request.method == 'POST':
        url = request.form.get('url')
        if not url:
            return render_template('index.html', error="URLを入力してください。")
        
        print(f"URLを受け取りました: {url}")
        results = scrape_images(url)
        print(f"結果: {results}")
        
        return render_template('index.html', results=results, url=url)

    return render_template('index.html')

# サーバー上で直接実行されることはないため、app.run()の呼び出しは不要になります。
# もしローカルでテストしたい場合は、この部分を元に戻してください。
# if __name__ == '__main__':
#     app.run(debug=True)