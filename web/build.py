import base64, pathlib
here = pathlib.Path(__file__).parent
t = (here / 'template.html').read_text()
glue = (here / 'node_modules/manifold-3d/manifold.js').read_text()
assert glue.rstrip().endswith('export default Module;')
glue = glue.rstrip()[:-len('export default Module;')]
geom = (here / 'frame-geom.js').read_text().replace("if (typeof module !== 'undefined') module.exports = FrameGeom;", '')
wasm = base64.b64encode((here / 'node_modules/manifold-3d/manifold.wasm').read_bytes()).decode()
for k, v in (('/*WASM_B64*/', wasm), ('/*FRAME_GEOM*/', geom), ('/*MANIFOLD_GLUE*/', glue)):
    assert t.count(k) == 1; t = t.replace(k, v)
(here / 'photo-frame-maker.html').write_text(t)
print(len(t) // 1024, 'KB')
