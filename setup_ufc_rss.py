import qbittorrentapi
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def setup_ufc_rss():
    try:
        conn = qbittorrentapi.Client(host='localhost', port=8080)
        conn.auth_log_in()
        logging.info("Connected to qBittorrent.")

        # 1. Add RSS Feed (Using Jackett 'all' endpoint for maximum coverage)
        # category 5000=TV, 2000=Movies, 5070=Sports (checking generic search first)
        rss_url = "http://192.168.1.132:9117/api/v2.0/indexers/all/results/torznab/api?apikey=d2ffpmovb2snm9trzthqmkhzxf8ks5po&t=search&q=UFC+1080p"
        feed_name = "UFC_Tracker"
        
        try:
            conn.rss_add_feed(url=rss_url, path=feed_name)
            logging.info(f"RSS Feed '{feed_name}' added.")
        except Exception as e:
            logging.warning(f"Feed might already exist: {e}")

        # 2. Configure AutoDownloader Rule
        rule_name = "UFC_Auto_Download"
        rule_config = {
            "enabled": True,
            "mustContain": "UFC.*(Main|Prelim).*(1080p|2160p|4k)",  # Regex for UFC + Main/Prelim + High Res
            "mustNotContain": "720p|SD|CAM|TS",
            "useRegex": True,
            "affectedFeeds": [rss_url],
            "savePath": "/data/complete/UFC/",
            "smartFilter": True,  # Avoid duplicates
            "episodeFilter": "",
        }

        conn.rss_set_rule(rule_name=rule_name, rule_def=rule_config)
        logging.info(f"AutoDownloader rule '{rule_name}' configured.")
        
        # 3. Force RSS Refresh
        conn.rss_refresh_item(item_path=feed_name)
        logging.info("RSS Feed refreshed.")

    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    setup_ufc_rss()
