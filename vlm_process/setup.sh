apt update
apt install nano
apt install -y tmux
pip install -r requirements.txt
tmux new -s test_session -d nano config.py