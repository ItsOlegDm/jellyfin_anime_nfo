import os
import time
import xml.etree.ElementTree as ET
import requests
import logging

DIRECTORY_TO_WATCH = "/run/media/itsolegdm/file-trashbin/itsolegdm/jellyfin/anime"
PROCESSED_FILES_LOG = "processed_files.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_processed_files():
    if os.path.exists(PROCESSED_FILES_LOG):
        with open(PROCESSED_FILES_LOG, 'r') as file:
            return set(line.strip() for line in file.readlines())
    return set()

def save_processed_file(filepath):
    with open(PROCESSED_FILES_LOG, 'a') as file:
        file.write(filepath + '\n')
    logging.info(f"Processed file saved: {filepath}")

def process_nfo_file(filepath, titles, file_position):
    try:
        filename = os.path.splitext(os.path.basename(filepath))[0].replace('_', ' ')
        tree = ET.parse(filepath)
        root = tree.getroot()

        title_element = root.find('title')
        episode = root.find('episode')

        if title_element is None:
            title_element = ET.SubElement(root, 'title')

        episode_name = titles.get(file_position)
        if episode_name:
            logging.info(f"Updating title in {filepath} to '{episode_name}'")
            title_element.text = episode_name
        else:
            logging.info(f"No title found for episode {file_position + 1}, using filename '{filename}'")
            title_element.text = filename

        if episode is None:
            episode = ET.SubElement(root, 'episode')
        if episode.text != str(file_position + 1):
            logging.info(f"Updating episode in {filepath} from '{episode.text}' to '{file_position + 1}'")
            episode.text = str(file_position + 1)

        tree.write(filepath, encoding='utf-8', xml_declaration=True)
        logging.info(f"Processed {filepath} successfully.")
    except Exception as e:
        logging.error(f"Error processing {filepath}: {e}")

def get_mal_id(media_id):
    query = '''query($id: Int){Media(id: $id){idMal}}'''

    variables = {
        'id': int(media_id)
    }

    url = 'https://graphql.anilist.co'

    response = requests.post(url, json={'query': query, 'variables': variables}).json()
    logging.info(response)
    idMal = response.get('data').get('Media').get('idMal')
    time.sleep(10)
    
    return idMal

def get_tvshow_titles(filepath):
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        title = root.find('title')
        anilistid = root.find('anilistid')

        titles = {}
        if title is not None:
            mal_id = None
            if anilistid is not None:
                mal_id = get_mal_id(anilistid.text)
            if mal_id is not None:
                resp = requests.get(f"https://api.jikan.moe/v4/anime?q={title.text}").json()
                if resp.get("data") is not None and len(resp.get("data")) > 0:
                    mal_id = resp.get("data")[0]["mal_id"]
            if mal_id is not None:
                resp = requests.get(f"https://api.jikan.moe/v4/anime/{mal_id}/episodes").json()
                episodes = resp.get("data")
                if episodes is not None and len(episodes) > 0:
                    for i, episode in enumerate(episodes):
                        titles[i] = episode.get("title")
            logging.info(f"Retrieved titles for {title.text} successfully.")
        return titles
    except Exception as e:
        logging.error(f"Error fetching titles from API: {e}")
        return {}

def monitor_directory(directory):
    processed_files = load_processed_files()

    while True:
        for root, dirs, files in os.walk(directory):
            if "tvshow.nfo" in files:
                tvshow_nfo_path = os.path.join(root, "tvshow.nfo")

                if tvshow_nfo_path not in processed_files:
                    titles = get_tvshow_titles(tvshow_nfo_path)

                    nfo_files = sorted([f for f in files if f.endswith('.nfo') and f != "tvshow.nfo"])

                    for i, file in enumerate(nfo_files):
                        filepath = os.path.join(root, file)
                        logging.info(f"Starting to check episode {i + 1} for file: {filepath}")
                        process_nfo_file(filepath, titles, i)
                        save_processed_file(filepath)

                    save_processed_file(tvshow_nfo_path)
                    processed_files.add(tvshow_nfo_path)
                    logging.info(f"Processed directory: {root}")

        time.sleep(60)

if __name__ == "__main__":
    logging.info("Starting directory monitoring.")
    monitor_directory(DIRECTORY_TO_WATCH)
