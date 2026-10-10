"""Fill known punctuation aliases with existing glyphs; never replace platform textures."""
import argparse,copy,pathlib,os
import UnityPy
p=argparse.ArgumentParser();p.add_argument('input',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);a=p.parse_args();env=UnityPy.load(str(a.input));o=next(x for x in env.objects if x.type.name=='MonoBehaviour');font=o.read_typetree();chars=font['m_CharacterTable'];bycode={x['m_Unicode']:x for x in chars};aliases={'!':'！','·':'•','・':'•'}
for target,source in aliases.items():
 if ord(target) not in bycode:
  c=copy.deepcopy(bycode[ord(source)]);c['m_Unicode']=ord(target);chars.append(c)
o.save_typetree(font);a.output.parent.mkdir(parents=True,exist_ok=True);tmp=a.output.with_name(a.output.name+'.tmp');assert not tmp.exists(),str(tmp);tmp.write_bytes(env.file.save(packer='lz4'));after=UnityPy.load(str(tmp));f=next(x for x in after.objects if x.type.name=='MonoBehaviour').read_typetree();c={x['m_Unicode']:x for x in f['m_CharacterTable']}
assert all(n in c for n in range(32,127))
for target,source in aliases.items():assert c[ord(target)]['m_GlyphIndex']==c[ord(source)]['m_GlyphIndex']
# Atlases and all other serialized objects must be byte-identical.
new={(x.assets_file.name,x.path_id):x.get_raw_data() for x in after.objects};assert all(x.get_raw_data()==new[(x.assets_file.name,x.path_id)] for x in env.objects if x.path_id!=o.path_id)
os.replace(tmp,a.output)
print('Verified punctuation aliases, existing glyphs and unchanged atlas:',a.output)
