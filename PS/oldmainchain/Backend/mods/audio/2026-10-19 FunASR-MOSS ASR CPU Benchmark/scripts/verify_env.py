import sys
print('python', sys.version.split()[0])
try:
    import torch
    print('torch', torch.__version__)
    print('default_threads', torch.get_num_threads())
    print('mkl', torch.backends.mkl.is_available())
    print('openmp', torch.backends.openmp.is_available())
except Exception as e:
    print('torch import failed:', repr(e))
try:
    import torchaudio
    print('torchaudio', torchaudio.__version__)
except Exception as e:
    print('torchaudio import failed:', repr(e))
try:
    import funasr
    print('funasr', funasr.__version__)
except Exception as e:
    print('funasr import failed:', repr(e))
try:
    import modelscope
    print('modelscope', modelscope.__version__)
except Exception as e:
    print('modelscope import failed:', repr(e))
try:
    import transformers
    print('transformers', transformers.__version__)
except Exception as e:
    print('transformers import failed:', repr(e))
try:
    import huggingface_hub
    print('huggingface_hub', huggingface_hub.__version__)
except Exception as e:
    print('huggingface_hub import failed:', repr(e))
