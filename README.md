# Roskomnadzor prohibited resources registry checker

```
git clone https://github.com/nixikanius/rkn-checker
cd rkn-checker
```

```
virtualenv -p python3 venv
source venv/bin/activate
pip install -r venv-requirements.txt
```

```
python checker.py fetch
python checker.py check 159.89.5.4
python checker.py check sslproxy.teamwork.com
python checker.py check 159.89.5.4 sslproxy.teamwork.com
```


```
docker build -t rkn-checker .
docker run rkn-checker 159.89.5.4
docker run rkn-checker sslproxy.teamwork.com
docker run rkn-checker 159.89.5.4 sslproxy.teamwork.com
docker run --env REGISTRY_URL='https://github.com/zapret-info/z-i/archive/master.zip' rkn-checker 159.89.5.4 sslproxy.teamwork.com
```
