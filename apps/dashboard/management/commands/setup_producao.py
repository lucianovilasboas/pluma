from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.corretores.models import CorretorLLM, PoolCorrecao, PoolCorretor, ProvedorLLM
from apps.redacoes.models import TemaRedacao

_TEMAS = [
    {
        "titulo": "Perspectivas acerda do envelhecimento da população brasileira",
        "texto": (
            "TEXTOS MOTIVADORES\n"
            "TEXTO I\n"
            "Em 2022, o total de pessoas com 65 anos de idade ou mais no país chegou a 10,9% da "
            'população, com alta de 57,4% frente a 2010, quando esse contingente era 7,4% da '
            "população. É o que revelam os resultados do universo da população do Brasil "
            "desagregada por idade e sexo do Censo Demográfico 2022. “O Estatuto do Idoso define "
            "como idoso a pessoa de 60 anos ou mais. O corte de 65 anos ou mais foi utilizado "
            "nessa análise para manter comparabilidade internacional e com outras pesquisas que "
            "utilizam essa faixa etária, como de mercado de trabalho”, justifica a gerente de "
            "Estudos e Análises da Dinâmica Demográfica do IBGE. O aumento da população de 65 "
            "anos ou mais e a diminuição da parcela da população de até 14 anos no mesmo período, "
            "que passou de 24,1% para 19,8%, evidenciam o franco envelhecimento da população "
            "brasileira.\n\n"
            "GOMES, I.; BRITTO, V. Censo 2022. Disponível em: "
            "https://agenciadenoticias.ibge.gov.br. Acesso em: 21 maio 2025 "
            "(adaptado).\n"
            "TEXTO II\n"
            "Um movimento na internet, contrário ao pictograma com a bengala para os idosos, "
            "iniciou uma campanha para modificar essa imagem. A empreitada coletiva acabou com a "
            "elaboração de um novo desenho, uma figura mais altiva, ao lado da inscrição “60+”.\n\n"
            "À esquerda: idoso curvado usando uma bengala. À direita: idoso em pé, sem bengala, "
            "com a postura ereta.\n"
            "Disponível em: www12.senado.leg.br. Acesso em: 21 maio 2025.\n"
            "TEXTO III\n"
            "A velhice é tempo de se retratar consigo mesma, de falar da doença, da sexualidade, "
            "do tédio e da liberdade de não se encaixar mais nas expectativas sociais. “A velhice "
            "não é doença. É destino”, escreve Rita Lee. Mas ela mesma mostra que esse destino "
            "não é sinônimo de mero encaminhamento para o fim — é campo de novas escolhas, "
            "inclusive a de desafiar estereótipos reservados para essa fase da vida.\n\n"
            "A atriz Fernanda Montenegro, 95 anos, oferece em suas memórias uma síntese luminosa "
            "desse gesto de habitar o tempo com dignidade: “A velhice é o tempo em que a vida já "
            "foi vivida e, por isso mesmo, pode finalmente ser olhada de frente, sem o pânico do "
            "ineditismo”.\n\n"
            "Disponível em: https://rascunho.com.br. Acesso em: 17 maio 2025.\n"
            "TEXTO IV\n"
            "Um novo estereótipo: o “velho ativo”, saudável e com recursos pressiona o “velho "
            "inativo”, doente e pobre. Nem todos os idosos têm recursos à disposição para aderir "
            "a essa corrida.\n\n"
            "Gráfico em pizza. Pessoas de 65 a 74 anos. 34% contribuem para os gastos, mas não "
            "são os mantenedores principais. 38% são a principal renda, mas conta com outras "
            "rendas. 28% sustentam a casa sozinhos.\n"
            "Disponível em: g1.globo.com. Acesso em: 4 jun. 2025 (adaptado).\n"
            "TEXTO V\n"
            "Dona Maria Rita era tão antiga que na casa da filha estavam habituados a ela como a "
            "um móvel velho. Ela não era novidade para ninguém. Mas nunca lhe passara pela cabeça "
            "que era uma solitária. Só que não tinha nada para fazer. Era um lazer forçado que em "
            "certos momentos se tornava lancinante: nada tinha a fazer no mundo. Senão viver como "
            "um gato, como um cachorro. Seu ideal era ser dama de companhia de alguma senhora, "
            "mas isso nem se usava mais e mesmo ninguém acreditaria nos seus fortes setenta e sete "
            "anos, pensariam que era uma fraca. Não fazia nada, fazia só isso: ser velha. Às vezes "
            "ficava deprimida: achava que não servia a nada, não servia sequer a Deus.\n\n"
            "LISPECTOR, C. Onde estivestes de noite. Rio de Janeiro: Francisco Alves, 1974.\n"
            "TEXTO VI\n"
            "Quem tem direito de viver mais?\n\n"
            "O documentário Quantos dias. Quantas noites busca investigar quem, afinal, tem "
            "direito a uma vida longa no Brasil. “São inúmeros os marcadores que definem quem "
            "vai viver e quem vai sucumbir diante de uma realidade imposta por um sistema bastante "
            "perverso”, afirma o diretor do documentário.\n\n"
            "“O envelhecimento leva a maioria das pessoas a um declínio funcional. Mas, se você "
            "chega aos 75 tendo acumulado desigualdades, principalmente pelo racismo, é muito "
            "difícil sobreviver com qualidade de vida”, diz um médico gerontólogo.\n\n"
            "Disponível em: g1.globo.com. Acesso em: 10 jun. 2025 (adaptado).\n"
            "A partir da leitura dos textos motivadores e com base nos conhecimentos construídos "
            "ao longo de sua formação, redija um texto dissertativo-argumentativo em modalidade "
            "escrita formal da língua portuguesa sobre o tema “Perspectivas acerca do "
            "envelhecimento na sociedade brasileira”, apresentando proposta de intervenção que "
            "respeite os direitos humanos. Selecione, organize e relacione, de forma coerente e "
            "coesa, argumentos e fatos para a defesa de seu ponto de vista."
        ),
    },
    {
        "titulo": "O desafio de combater o preconceito linguístico no Brasil.",
        "texto": (
            "TEXTOS MOTIVADORES\n"
            "TEXTO I\n"
            "O preconceito linguístico é, segundo o professor, linguista e filólogo Marcos Bagno, "
            "todo juízo de valor negativo (de reprovação, de repulsa ou mesmo de desrespeito) às "
            "variedades linguísticas de menor prestígio social. No Brasil, o preconceito "
            "linguístico é muito perceptível em dois âmbitos: no regional e no socioeconômico.\n\n"
            "No primeiro caso, indivíduos de grandes centros populacionais, os quais monopolizam "
            "cultura, mídia e economia, como Sudeste e Sul, manifestam algum tipo de aversão ao "
            "sotaque ou aos regionalismos típicos de regiões mais pobres, como Nordeste, Norte e "
            "Centro-Oeste. No segundo caso, membros das classes mais pobres são discriminados por "
            "dominarem apenas as variedades linguísticas mais informais e de menor prestígio, "
            "geralmente devido ao acesso limitado à educação formal e cultura.\n\n"
            "Disponível em: https://brasilescola.uol.com.br/portugues/preconceito-linguistico.htm. "
            "Acesso em: 19 ago. 2022 (adaptado).\n"
            "TEXTO II\n"
            "Uma jovem pensando sobre variação linguística, regionalismos, gírias, desvios da "
            "norma padrão, etc.\n"
            "Disponível em: https://novaescola.org.br/planos-de-aula/fundamental/9ano/lingua-"
            "portuguesa/a-norma-padrao-e-o-preconceito-linguistico/3583. Acesso em: 19 ago. 2022.\n"
            "TEXTO III\n"
            "Como a principal causa do preconceito linguístico é a crença de que só existe um tipo "
            "certo de expressão, pessoas que não se encaixam no padrão são vistas como erradas e "
            "podem, por consequência, ser vítimas desse tipo de discriminação.\n\n"
            "Algumas das consequências para quem sofre preconceito linguístico podem ser:\n\n"
            "- Desenvolver medo de falar em público e de se expressar, temendo o que os outros "
            "pensam;\n\n"
            "- Ser excluído socialmente por falar um dialeto diferente ou "
            "com sotaque diferente;\n\n"
            "- Prejuízos à autoestima, já que a pessoa começa a acreditar "
            "que ela é errada;\n\n"
            "- Dificuldade de conseguir um emprego, especialmente se "
            "requerer comunicação formal.\n\n"
            "Disponível em: https://ead.uri.br/blog/preconceito-linguistico. "
            "Acesso em: 21 ago. 2022 (adaptado).\n"
            "A partir da leitura dos textos motivadores e com base nos conhecimentos construídos "
            "ao longo de sua formação, redija um texto dissertativo-argumentativo em modalidade "
            "escrita formal da língua portuguesa sobre o tema “O desafio de combater o preconceito "
            "linguístico no Brasil”, apresentando proposta de intervenção que respeite os direitos "
            "humanos. Selecione, organize e relacione, de forma coerente e coesa, argumentos e "
            "fatos para a defesa de seu ponto de vista."
        ),
    },
    {
        "titulo": "Desafios para promoção da cultura de adoção no Brasil.",
        "texto": (
            "TEXTOS MOTIVADORES\n"
            "TEXTO I\n"
            "O Brasil tem, efetivamente, 4,9 mil menores esperando por adoção e 42.546 pessoas ou "
            "casais que pretendem adotar uma criança. Apesar da aparente abundância de "
            "interessados em adotar uma criança ou adolescente, o processo é demorado e "
            "complicado. Isso ocorre, sobretudo, porque a maioria dos candidatos a adotantes faz "
            "exigências e demonstra preferências muito parecidas. Nesse sentido, há muitos "
            "candidatos concorrendo pela adoção das mesmas crianças, enquanto muitas esperam até "
            "atingirem a maioridade e perderem o direito à adoção.\n\n"
            "As preferências para a adoção são, em sua maioria, crianças brancas, sem irmãos, sem "
            "deficiência física ou cognitiva e com baixa idade. Grande parte dos adotantes prefere "
            "adotar crianças com até 2 anos de idade. Quanto mais velha a criança, menor a chance "
            "de adoção. As crianças com mais de 10 anos têm chances bem pequenas de serem "
            "adotadas.\n\n"
            "Disponível em: https://mundoeducacao.uol.com.br/sociologia/adocao-no-brasil.htm. "
            "Acesso em: 16 out. 2022 (adaptado).\n"
            "TEXTO II\n"
            "Adotar. Onde começa um novo. Quando uma criança ou um adolescente é adotado, oferece "
            "muito mais do que amor: oferece uma nova vida. 25 de maio, Dia Nacional da Adoção.\n"
            "Disponível em: https://www.trt8.jus.br/noticias/2021/trt8-adere-campanha-celebrando-"
            "o-dia-nacional-da-adocao. Acesso em: 22 out. 2022.\n"
            "TEXTO III\n"
            "Um entrave importante no processo de adoção é a burocracia legal existente. O "
            "Estatuto da Criança e do Adolescente (ECA), instituído pela Lei nº 8.069, de 13 de "
            "julho de 1990, dispõe em seu inciso 10 do artigo 47 que: “O prazo máximo para "
            "conclusão da ação de adoção será de 120 (cento e vinte) dias, prorrogável uma única "
            "vez por igual período, mediante decisão fundamentada da autoridade judiciária”.\n\n"
            "O diagnóstico do CNJ (Conselho Nacional de Justiça), porém, mostra que "
            "aproximadamente 43,5% das ações de adoção realizadas foram concluídas em mais de 240 "
            "dias, de acordo com os dados do Sistema Nacional de Adoção e Acolhimento.\n\n"
            "Disponível em: https://www.gazetadopovo.com.br/vida-e-cidadania/desafios-da-adocao-"
            "no-brasil-idade-da-crianca-burocracia-e-entrega-legal/. Acesso em: 15 out. 2022 "
            "(adaptado).\n"
            "A partir da leitura dos textos motivadores e com base nos conhecimentos construídos "
            "ao longo de sua formação, redija um texto dissertativo-argumentativo em modalidade "
            "escrita formal da língua portuguesa sobre o tema “Desafios para a promoção da cultura "
            "de adoção no Brasil”, apresentando proposta de intervenção que respeite os direitos "
            "humanos. Selecione, organize e relacione, de forma coerente e coesa, argumentos e "
            "fatos para a defesa de seu ponto de vista."
        ),
    },
]

_CORRETORES = [
    {"nome": "GPT-4o", "modelo": "gpt-4o", "provedor": "OpenAI"},
    {"nome": "DeepSeek Chat", "modelo": "deepseek-chat", "provedor": "DeepSeek"},
]

_POOL_NOME = "Banca Padrão"


class Command(BaseCommand):
    help = "Configuração inicial de produção: temas, provedores LLM, corretores e banca."

    def add_arguments(self, parser):
        parser.add_argument("--openai-key", default="", help="Chave de API da OpenAI")
        parser.add_argument("--deepseek-key", default="", help="Chave de API da DeepSeek")
        parser.add_argument(
            "--deepseek-url", default="https://api.deepseek.com", help="Base URL da DeepSeek"
        )

    def handle(self, *args, **options):
        openai_key = options["openai_key"].strip()
        deepseek_key = options["deepseek_key"].strip()
        deepseek_url = options["deepseek_url"]

        self._criar_temas()
        provedores = self._criar_provedores(openai_key, deepseek_key, deepseek_url)
        if provedores:
            corretores_llm = self._criar_corretores_llm(provedores)
            self._criar_pool(corretores_llm)
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nNenhum provedor configurado (--openai-key e --deepseek-key omitidos). "
                    "Pule a criação de corretores e banca."
                )
            )

        self.stdout.write(self.style.SUCCESS("\nConfiguração de produção concluída."))
        self._exibir_resumo()

    def _criar_temas(self):
        self.stdout.write("\n=== Temas de redação ===")
        for dados in _TEMAS:
            tema, created = TemaRedacao.objects.get_or_create(
                titulo=dados["titulo"],
                defaults={"texto": dados["texto"], "ativo": True},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  + {tema.titulo}"))
            else:
                tema.texto = dados["texto"]
                tema.ativo = True
                tema.save(update_fields=["texto", "ativo"])
                self.stdout.write(f"  = {tema.titulo} (atualizado)")

    def _criar_provedores(self, openai_key: str, deepseek_key: str, deepseek_url: str):
        self.stdout.write("\n=== Provedores LLM ===")

        provedores: dict[str, ProvedorLLM] = {}

        if openai_key:
            provedor, created = ProvedorLLM.objects.get_or_create(
                nome="OpenAI",
                defaults={"api_key": openai_key, "base_url": "", "ativo": True},
            )
            if not created:
                provedor.api_key = openai_key
                provedor.base_url = ""
                provedor.ativo = True
                provedor.save(update_fields=["api_key", "base_url", "ativo"])
            self.stdout.write(self.style.SUCCESS(f"  {'+' if created else '='} OpenAI"))
            provedores["OpenAI"] = provedor

        if deepseek_key:
            provedor, created = ProvedorLLM.objects.get_or_create(
                nome="DeepSeek",
                defaults={"api_key": deepseek_key, "base_url": deepseek_url, "ativo": True},
            )
            if not created:
                provedor.api_key = deepseek_key
                provedor.base_url = deepseek_url
                provedor.ativo = True
                provedor.save(update_fields=["api_key", "base_url", "ativo"])
            self.stdout.write(self.style.SUCCESS(f"  {'+' if created else '='} DeepSeek"))
            provedores["DeepSeek"] = provedor

        return provedores

    def _criar_corretores_llm(self, provedores: dict[str, ProvedorLLM]):
        self.stdout.write("\n=== Corretores LLM ===")

        corretores: dict[str, CorretorLLM] = {}

        for dados in _CORRETORES:
            nome_provedor = dados["provedor"]
            if nome_provedor not in provedores:
                continue
            provedor = provedores[nome_provedor]
            corretor, created = CorretorLLM.objects.get_or_create(
                nome=dados["nome"],
                defaults={"modelo": dados["modelo"], "provedor": provedor},
            )
            if not created:
                corretor.modelo = dados["modelo"]
                corretor.provedor = provedor
                corretor.save(update_fields=["modelo", "provedor"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {'+' if created else '='} {corretor.nome} "
                    f"({corretor.modelo})"
                )
            )
            corretores[dados["nome"]] = corretor

        return corretores

    def _criar_pool(self, corretores: dict[str, CorretorLLM]):
        self.stdout.write("\n=== Banca de correção ===")

        pool, created = PoolCorrecao.objects.get_or_create(
            nome=_POOL_NOME,
            defaults={"metodo": "mediana", "ativo": True},
        )
        if not created:
            pool.ativo = True
            pool.save(update_fields=["ativo"])

        PoolCorretor.objects.filter(pool=pool).delete()

        for ordem, (nome, corretor) in enumerate(corretores.items()):
            PoolCorretor.objects.create(
                pool=pool,
                tipo="llm",
                corretor_llm=corretor,
                peso=1.0,
                ordem=ordem,
            )
            self.stdout.write(f"  + {nome} (ordem={ordem})")

        PoolCorrecao.objects.filter(ativo=True).exclude(pk=pool.pk).update(ativo=False)

        status = "criada" if created else "recriada"
        self.stdout.write(self.style.SUCCESS(f"  Banca '{_POOL_NOME}' {status} e ativada."))

    def _exibir_resumo(self):
        n_temas = TemaRedacao.objects.count()
        n_provedores = ProvedorLLM.objects.filter(ativo=True).count()
        n_corretores = CorretorLLM.objects.count()
        pool_ativa = PoolCorrecao.objects.filter(ativo=True).first()

        self.stdout.write("\nResumo:")
        self.stdout.write(f"  Temas ativos:     {n_temas}")
        self.stdout.write(f"  Provedores ativos: {n_provedores}")
        self.stdout.write(f"  Corretores LLM:   {n_corretores}")
        if pool_ativa:
            self.stdout.write(f"  Banca ativa:      {pool_ativa.nome}")
