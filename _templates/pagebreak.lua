-- pandoc lua filter: 本文中の \newpage を Word の改ページに変換する
function RawBlock(el)
  if el.text:match("\\newpage") then
    if FORMAT == "docx" then
      return pandoc.RawBlock("openxml",
        '<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    elseif FORMAT == "html" or FORMAT == "html5" then
      return pandoc.RawBlock("html", '<div style="page-break-after: always;"></div>')
    end
  end
  return el
end
