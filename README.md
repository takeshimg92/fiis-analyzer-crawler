# Análise de FIIs (Fundos Imobiliários)

Utiliza Selenium para obter dados de fundos imobiliários, processá-los, e aplicar filtros a serem decididos pelo usuário.
* Os dados dos fundos são obtidos do [Funds Explorer](https://www.fundsexplorer.com.br/ranking);
* Os dados de vacância, que não são mais disponibilizados no Funds Explorer, são puxados do www.meusdividendos.com. 
* A tabela de FIIs é um Pandas DataFrame. Os filtros devem ser construídos e aplicados diretamente no código. Por exemplo:

```python
fiis = fiis[fiis["patrimonio_liquido"] > 0]
fiis = fiis[fiis["p/vp"] < 10] 
```

* Ao final, construo um score para cada FII. Mais detalhes nos notebooks.
* Ao rodar o arquivo `scorer.py`, ele gerará um arquivo da forma `fundos_imobiliarios_<data>.xlsx` em que `<data>` é uma string na forma `YYYY-MM-DD`. Esse arquivo pode ser usado para análises posteriores.