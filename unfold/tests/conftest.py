import os
import sys

# 어느 폴더에서 pytest 를 돌려도 hanil_unfold 를 찾게 한다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
