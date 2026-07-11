# Third Party Notices

This file records all third-party code reused in PaperAgent, per Re4 Map §8.6 rules.

## AutoResearchClaw (MIT License)

- **Source**: `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\mcp\`
- **Files reused**: `tools.py` (tool definition pattern), `server.py` (handler routing + run_id validation)
- **License**: MIT — Copyright (c) 2026 Aiming Lab
- **Modifications**: Renamed tools to PaperAgent capability names; replaced pipeline-specific
  handlers with PaperAgent service calls; added read/write permission layer.
- **Date**: 2026-07-10 (Re4.4)

### MIT License Text

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
