def escape(text: str):
    mark = [
        '`',
        '_',
        '*'
    ]
    for item in mark:
        text = text.replace(item, f'\u200b{item}')
    return text


def codeblock(text: str, lang=""):
    return f"```{lang}\n{text}```"
