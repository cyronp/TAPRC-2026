# TAPRC-2026

Este repositório contém a implementação das Azure Functions solicitadas na atividade da disciplina TAPRC-2026.

## Equipe

* Caio de Souza - [caiodesouza.cds@gmail.com/[CaioSouza07.github.com](https://github.com/CaioSouza07)]
* Carlos Deretti - [Email/GitHub]
* Mathias Gruber - [mathigmtk2gmail.com/[Mathias-GMTK.github.com](https://github.com/Mathias-GMTK)]
* Vitor Henrique - [Email/GitHub]
* Samuel de Souza - [Samueldesouza200512@gmail.com/[Shuraza.github.com](https://github.com/Shuraza)]

---

## Sobre o Projeto

O projeto é composto por Azure Functions desenvolvidas para demonstrar o uso de diferentes gatilhos (triggers) e a comunicação entre funções.

<details>
<summary>1. Timer Trigger - Log Simples</summary>

### Descrição
Função executada automaticamente em intervalos definidos via expressão CRON.

### Funcionamento
A função é disparada pelo temporizador e executa apenas uma instrução para imprimir uma mensagem de log no terminal/console do ambiente de execução.
</details>

<details>
<summary>2. HTTP Trigger - Leitura de Parâmetro</summary>

### Descrição
Função exposta via protocolo HTTP acessível por requisições do tipo GET.

### Funcionamento
Recebe um parâmetro enviado através da URL (query string), processa a requisição e retorna o valor digitado diretamente na tela/resposta HTTP.
</details>

<details>
<summary>3. Timer Trigger - Integração HTTP</summary>

### Descrição
Função baseada em tempo que atua como cliente HTTP para outra Azure Function.

### Funcionamento
É disparada periodicamente por um temporizador, realiza uma chamada HTTP para uma segunda função e exibe a resposta recebida, que contém a informação enviada acrescida de um texto de identificação.
</details>
