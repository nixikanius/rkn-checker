# Roskomnadzor ban registry checker

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
python check.py fetch
python check.py check 159.89.5.4
python check.py check sslproxy.teamwork.com
python check.py check 159.89.5.4 sslproxy.teamwork.com
```
