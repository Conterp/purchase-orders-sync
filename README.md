# PURCHASE-ORDERS-SYNC

Pipeline automatizado para sincronizar os **pedidos de compra do Bimer (Alterdata)** com o board **Conterp - Pedidos de Compra** no Monday.com, mantendo um item por item de pedido no semestre vigente.

---

## O que ele faz

- Autentica no Bimer e busca os pedidos do semestre vigente (status Aberto, Atendido e Cancelado)
- Gera a chave única de cada item (`{id_pedido}_{id_item}`) e compara com as chaves já existentes no Monday
- Enriquece apenas os itens novos com fornecedor, produto e centros de custo
- Prepara os registros (VALOR AF ÚNICO somente na primeira linha de uma AF totalmente nova, previsão de pagamento = emissão + 7 dias, "Gerado por" a partir da descrição)
- Cria os itens no grupo do mês de emissão (ou em **Canceladas**)
- Audita o board: remove duplicados (mantém o menor ID) e órfãos (chave fora do Bimer), atualiza status divergentes e move cancelados para **Canceladas**
- Concilia Bimer × Monday por grupo e envia o resumo ao webhook n8n (mensagem de WhatsApp)

### Proteções

- Escritas no Monday que falham com resultado incerto (timeout, HTTP 5xx, sem confirmação) **não são repetidas** e interrompem a etapa (`RESULTADO_INCERTO`) para evitar duplicidade
- Se o item que carrega o VALOR AF ÚNICO falhar, os demais itens da mesma AF são bloqueados
- A atualização de status só roda se as exclusões terminarem sem erro
- Etapas de leitura (auditoria e conciliação) não alteram o board

---

## Estrutura

```
purchase-orders-sync/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── src/
    ├── main.py
    ├── config/
    │   └── settings.py              # envs, grupos mensais, mapeamento de colunas
    ├── shared/
    │   ├── logger.py
    │   ├── normalize_text.py
    │   ├── retry.py
    │   └── chunks.py
    ├── bimer/
    │   ├── api_client.py
    │   ├── login.py
    │   ├── date_periods.py
    │   ├── build_unique_key.py
    │   ├── fetch_purchase_orders.py
    │   ├── fetch_suppliers.py
    │   ├── fetch_products.py
    │   ├── fetch_cost_centers.py
    │   ├── extract_order_items.py   # itens/chaves, status e grupo esperado
    │   └── prepare_records.py       # regras de negócio dos registros
    ├── monday/
    │   ├── api_client.py            # leitura com retry / escrita com RESULTADO_INCERTO
    │   ├── fetch_monday_keys.py
    │   ├── fetch_monday_groups.py
    │   ├── build_item_payload.py
    │   ├── create_items.py
    │   ├── delete_items.py
    │   └── update_items.py          # status + mover para Canceladas
    ├── sync/
    │   ├── compare_records.py
    │   ├── audit.py
    │   ├── run_cleanup.py
    │   └── reconcile.py
    ├── summary/
    │   └── build_summary.py         # resumo + mensagem WhatsApp
    └── webhook/
        └── send_to_n8n.py
```

---

## Etapas do pipeline

| Etapa | Descrição |
|---|---|
| 01 | Validar ambiente e token do Monday |
| 02 | Autenticar no Bimer |
| 03 | Calcular período do semestre |
| 04 | Buscar pedidos de compra (A, T, C) |
| 05 | Extrair itens e chaves únicas |
| 06 | Buscar chaves atuais no Monday |
| 07 | Comparar Bimer × Monday |
| 08–10 | Enriquecer fornecedores, produtos e centros de custo |
| 11 | Preparar registros |
| 12 | Montar payloads |
| 13 | Criar novos itens |
| 14 | Recarregar Monday |
| 15 | Auditar (duplicados, órfãos, status) |
| 16 | Limpeza e atualização de status |
| 17 | Conciliação final por grupo |
| 18 | Resumo |
| 19 | Enviar resumo ao n8n |

---

## Configuração

Copie `.env.example` para `.env` e preencha:

```env
BIMER_USERNAME=
BIMER_PASSWORD=
MONDAY_API_TOKEN=
N8N_SUMMARY_WEBHOOK_URL=
```

Dry-runs por ação (`false` = executa de verdade, `true` = apenas simula):

```env
PIPELINE_CREATE_DRY_RUN=false
PIPELINE_DELETE_DUPLICATE_DRY_RUN=false
PIPELINE_DELETE_ORPHAN_DRY_RUN=false
PIPELINE_UPDATE_STATUS_DRY_RUN=false
```

Os grupos mensais (`MONTH_GROUPS`), o grupo de canceladas e o mapeamento de colunas ficam em `src/config/settings.py`. Ao virar o ano, atualize `TARGET_YEAR` e os IDs dos grupos.

---

## Execução

### Local
```bash
python -u -m src.main
```

### Docker
```bash
docker compose up --build
```

### Autotestes por módulo
```bash
python -m src.bimer.fetch_purchase_orders
python -m src.monday.fetch_monday_keys
python -m src.monday.api_client
```

---

## 🤝 Autor

**João Carser**  
[github.com/JoaoCarser](https://github.com/JoaoCarser)