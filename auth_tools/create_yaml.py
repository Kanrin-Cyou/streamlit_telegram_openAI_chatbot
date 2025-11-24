#Thanks to Source: https://qiita.com/bassan/items/ed6d821e5ef680a20872

import csv
import yaml
from streamlit_authenticator.utilities.hasher import Hasher

users_csv_path = "user_info.csv"
config_yaml_path = "config.yaml"

## ユーザー設定の一覧が記述されたデータを読み込み
with open(users_csv_path, "r") as f:
    csvreader = csv.DictReader(f)
    users = list(csvreader)

## yaml 設定一覧が記述されたデータを読み込み
with open(config_yaml_path,"r") as f:
    yaml_data = yaml.safe_load(f)

## パスワードのハッシュ化
users_dict = {}
hasher = Hasher()
for user in users:
    print(user)
    user["password"] = hasher.hash(user["password"])
    tmp_dict = {
        "name": user["name"],
        "password": user["password"],
        "email": user["email"],
    }
    users_dict[user["id"]] = tmp_dict

## yaml 書き込み
yaml_data["credentials"]["usernames"] = users_dict
with open(config_yaml_path, "w") as f:
    yaml.dump(yaml_data, f)
    print("finished writing config.yaml")