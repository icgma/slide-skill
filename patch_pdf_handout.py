with open('tools/slide/src/slide_skill/pdf_handout.py', 'r') as f:
    code = f.read()

code = code.replace('pdf.cell(w, 5, line, new_x="LMARGIN", new_y="NEXT")', 'pdf.cell(w, 5, line, ln=1)')
code = code.replace('pdf.cell(w, 5, line.encode("ascii", "replace").decode(),', 'pdf.cell(w, 5, line.encode("ascii", "replace").decode(), ln=1)')
code = code.replace('new_x="LMARGIN", new_y="NEXT"', '')

with open('tools/slide/src/slide_skill/pdf_handout.py', 'w') as f:
    f.write(code)
