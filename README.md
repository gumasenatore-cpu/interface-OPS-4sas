# Portal de Operações 4SAS

Portal multipágina Streamlit com login Supabase, Boletim, APR e banco de fornecedores.

## Execução local

1. Use Python 3.10 ou superior e instale as dependências com `pip install -r requirements.txt` (Streamlit 1.50 ou superior).
2. Crie `.streamlit/secrets.toml` baseado em `.streamlit/secrets.toml.example`.
3. Use o URL e a chave publishable/anon do mesmo projeto Supabase que contém os usuários do portal.
4. Execute `streamlit run app.py`.

O cadastro público está desabilitado no portal. Crie os usuários no Supabase Auth e exija confirmação de e-mail conforme a política da organização. Recuperações de senha devem ser feitas pelo administrador no Supabase Auth; o fluxo de callback de recuperação ainda não está habilitado no Streamlit.

## Banco de fornecedores

Execute `supabase/fornecedores.sql` no SQL Editor do projeto Supabase usado pelo portal. A tabela permite leitura e inclusão apenas a usuários autenticados; não são concedidas permissões de atualização ou exclusão.

O banco do antigo app de fornecedores está em outro projeto Supabase. Os registros existentes não são transferidos por esse SQL. Exporte-os do projeto antigo e importe-os na tabela do projeto do portal após verificar o mapeamento das colunas.

## Importação administrativa do Google Places

Execute `povoar_fornecedores_google.py` somente em um ambiente administrativo confiável. Ele usa `SUPABASE_SERVICE_ROLE_KEY` e `GOOGLE_PLACES_API_KEY` do ambiente, nunca da página web. O upsert usa `google_place_id` para não duplicar resultados repetidos. Defina `FORNECEDORES_CIDADE` e `FORNECEDORES_UF` para escolher a localidade. Execute o SQL da tabela antes do script.

## Publicação no Streamlit Community Cloud

1. Publique o código no repositório GitHub conectado como `origin`.
2. No Streamlit Community Cloud, crie um app selecionando esse repositório, a branch publicada e `app.py` como arquivo principal.
3. Em **App settings > Secrets**, configure `SUPABASE_URL` e `SUPABASE_KEY` com os valores do projeto Supabase que contém os usuários e a tabela de fornecedores.
4. Não envie `.streamlit/secrets.toml` ao GitHub. O arquivo está no `.gitignore`; use os Secrets do Streamlit Cloud no deploy.

O vínculo do GitHub ao Streamlit Cloud, o deploy inicial e a execução do SQL precisam ser confirmados nas respectivas contas externas.