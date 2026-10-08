"""PDA 설비 위치(pda.js unityLocation)가 Unity FactoryRig.Layout과 같은 좌표를 내는지 확인한다.

두 곳에 같은 계산이 있어서, 한쪽만 바뀌면 PDA 위치 표시가 조용히 어긋난다.
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RIG = ROOT / "unity/ShiftLinkFactory/Assets/Scripts/FactoryRig.cs"


def csharp_layout():
    """기본 간격의 FactoryRig.BaseLayout 좌표식을 꺼낸다(f 접미사만 뗀다)."""
    source = RIG.read_text(encoding="utf-8")
    assert "public static float LayoutSpacing = 1;" in source
    layout = source.split("public static Vector3 Layout(", 1)[1].split("\n    }", 1)[0]
    assert "var position=BaseLayout(code,index,count,auxiliary);" in layout
    assert "return new Vector3(position.x*LayoutSpacing,position.y,position.z*LayoutSpacing);" in layout
    body = source.split("static Vector3 BaseLayout(", 1)[1].split("\n    }", 1)[0]
    vec = lambda s: [re.sub(r"(\d)f\b", r"\1", a) for a in s.split(",")]
    main = vec(re.search(r"if\(index>=0\) return new Vector3\((.+?)\);", body).group(1))
    cases = {c: vec(v) for c, v in re.findall(r'case "([\w-]+)": return new Vector3\((.+?)\);', body)}
    default = vec(re.search(r"default: return new Vector3\((.+?)\);", body).group(1))
    return main, cases, default


def test_pda_location_matches_unity_layout():
    main, cases, default = csharp_layout()
    assert set(cases) == {"GR-01", "GR-02", "HPU-01", "PDP-01", "CAU-01", "CV-02"}
    probes, expected = [], []
    for count in (4, 6, 9):
        route = [f"R{i}" for i in range(count)]
        rows = [(f"R{i}", "RT-01", i, 0) for i in (0, count - 1)]
        rows += [(f"A-{c}", c, -1, 0) for c in cases] + [("A-X", "XX-01", -1, 2)]
        for eq_id, code, index, aux in rows:
            env = {"count": count, "index": index, "auxiliary": aux}
            exprs = main if index >= 0 else cases.get(code, default)
            expected.append([round(eval(e, {}, env), 1) for e in exprs])
            probes.append({"eq": {"equipment_id": eq_id, "code": code}, "config": {"route": route}, "aux": aux})
    script = ("const {unityLocation}=require('./shiftlink/mes/web/pda.js');"
              "const probes=JSON.parse(require('fs').readFileSync(0,'utf8'));"
              "console.log(JSON.stringify(probes.map(p=>unityLocation(p.eq,p.config,p.aux))));")
    out = subprocess.run(["node", "-e", script], input=json.dumps(probes), capture_output=True,
                         text=True, encoding="utf-8", cwd=ROOT, check=True).stdout
    for text, want, probe in zip(json.loads(out), expected, probes):
        got = [round(float(v), 1) for v in re.search(r"X (\S+), Y (\S+), Z (\S+)\)", text).groups()]
        assert got == want, (probe, text, want)


def test_pda_handover_copy_node():
    result = subprocess.run(["node", "tests/pda_handover_copy.cjs"], capture_output=True,
                            text=True, encoding="utf-8", cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
