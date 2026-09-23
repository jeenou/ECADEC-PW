import pypdf
r = pypdf.PdfReader(r'C:\Program Files\DIgSILENT\PowerFactory 2026 SP3\localisation\en-GB\examples\MV_Distr\MV_Distr.pdf')
text = ''
for page in r.pages[:3]:
    text += (page.extract_text() or '') + '\n'
print(text[:3000])
