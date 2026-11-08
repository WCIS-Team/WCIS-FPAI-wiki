import json
import urllib.request

repos = ["AISHELL/AISHELL-1", "AudioLLMs/aishell_1_zh_test", "shenyunhang/AISHELL-1"]
out = []
for rid in repos:
    url = "https://huggingface.co/api/datasets/{}?full=true".format(rid)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=60))
        out.append("==== " + rid + " ====")
        out.append("downloads: {}  size_hint: {}".format(data.get("downloads"), data.get("cardData", {}).get("size_categories")))
        sib = data.get("siblings", [])
        out.append("total files: {}".format(len(sib)))
        wavs = [s for s in sib if s.get("rfilename", "").endswith((".wav", ".flac", ".m4a", ".mp3", ".opus"))]
        out.append("audio files: {}".format(len(wavs)))
        for s in wavs[:15]:
            out.append("  " + s["rfilename"])
        if len(wavs) > 15:
            out.append("  ... (more)")
    except Exception as e:
        out.append("==== " + rid + " ==== ERR " + repr(e))
with open(r"D:\yzd\llm\funasr\hf_aishell_detail.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("WROTE", len(out))
