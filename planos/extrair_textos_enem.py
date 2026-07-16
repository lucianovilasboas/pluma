"""
Script para construir o enem_temas.json a partir dos textos motivadores
coletados do coRedação.
"""

from __future__ import annotations

import json
from pathlib import Path

ENEM_TEXTS: dict[str, str] = {
    "1998-regular": """Redija um texto dissertativo, sobre o tema "Viver e Aprender", no qual você exponha suas ideias de forma clara, coerente e em conformidade com a norma culta da língua, sem se remeter a nenhuma expressão do texto motivador "O Que É O Que É". Dê um título a sua redação.

TEXTO 1:
(Letra da música "O que é, o que é" de Gonzaguinha)

Viver e não ter a vergonha de ser feliz
Cantar e cantar e cantar a beleza de ser um eterno aprendiz
Eu sei que a vida devia ser bem melhor e será
Mas isso não impede que eu repita
É bonita, é bonita e é bonita.""",

    "1999-regular": """Com base na leitura dos quadrinhos e depoimentos, redija um texto em prosa, do tipo dissertativo-argumentativo, sobre o tema: "Cidadania e participação social". Ao desenvolver o tema proposto, procure utilizar os conhecimentos adquiridos ao longo de sua formação. Depois de selecionar, organizar e relacionar os argumentos, fatos e opiniões apresentados em defesa de seu ponto de vista, elabore uma proposta de ação social.

TEXTO 2:
O encontro "Vem ser cidadão" reuniu 380 jovens de 13 Estados, em Faxinal do Céu (PR). Eles foram trocar experiências sobre o chamado protagonismo juvenil. O termo pode até parecer feio, mas essas duas palavras significam que o jovem não precisa de adulto para encontrar o seu lugar e a sua forma de intervir na sociedade. Ele pode ser protagonista.
"Para quem se revolta e quer agir", Folha de S. Paulo, 16/11/1998 (adaptado)

TEXTO 3:
Depoimentos de jovens: "Eu não sinto vergonha de ser brasileiro. Eu sinto muito orgulho. Mas eu sinto vergonha por existirem muitas pessoas acomodadas. A realidade está nua e crua. Tem de parar com o comodismo. Não dá para passar e ver uma criança na rua e achar que não é problema seu." (E.M.O.S., 18 anos, Minas Gerais) / "A maior dica é querer fazer. Se você é acomodado, fica esperando cair no colo, não vai acontecer nada." (C.S.Jr., 16 anos, Paraná) / "Ser cidadão não é só conhecer os seus direitos. É participar, ser dinâmico na sua escola, no seu bairro." (H.A., 19 anos, Amazonas)""",

    "2000-regular": """Com base na leitura da charge, do artigo da Constituição, do depoimento de A.J. e do trecho do livro O cidadão de papel, redija um texto em prosa, do tipo dissertativo-argumentativo, sobre o tema: "Direitos da criança e do adolescente: como enfrentar esse desafio nacional?"

TEXTO 2:
"É dever da família, da sociedade e do Estado assegurar à criança e ao adolescente, com absoluta prioridade, o direito à saúde, à alimentação, à cultura, à dignidade, ao respeito, à liberdade e à convivência familiar e comunitária, além de colocá-los a salvo de toda forma de negligência, discriminação, exploração, crueldade e opressão".
Artigo 227, Constituição da República Federativa do Brasil.

TEXTO 3:
Esquina da Avenida Desembargador Santos Neves com Rua José Teixeira, na Praia do Canto, área nobre de Vitória. A.J., 13 anos, morador de Cariacica, tenta ganhar algum trocado vendendo balas para os motoristas. "Venho para a rua desde os 12 anos. Não gosto de trabalhar aqui, mas não tem outro jeito. Quero ser mecânico."
A Gazeta, Vitória (ES), 9 de junho de 2000.

TEXTO 4:
Entender a infância marginal significa entender porque um menino vai para a rua e não à escola. Essa é, em essência, a diferença entre o garoto que está dentro do carro, de vidros fechados, e aquele que se aproxima do carro para vender chiclete ou pedir esmola. E essa é a diferença entre um país desenvolvido e um país de Terceiro Mundo.
Gilberto Dimenstein. O cidadão de papel. São Paulo, Ática, 2000. 19a. edição.""",

    "2001-regular": """Com base na leitura dos quadrinhos e dos textos, redija um texto dissertativo-argumentativo sobre o tema: "Desenvolvimento e Preservação Ambiental: como conciliar os interesses em conflito?"

TEXTO 2:
Estou indignado com a frase do presidente dos Estados Unidos, George Bush. "Somos os maiores poluidores do mundo, mas se for preciso poluiremos mais para evitar uma recessão na economia americana".
R. K., Ourinhos, SP. (Carta enviada à seção Correio da Revista Galileu. Ano 10, junho de 2001.)

TEXTO 3:
Conter a destruição das florestas se tornou uma prioridade mundial, e não apenas um problema brasileiro. Restam hoje, em todo o planeta, apenas 22% da cobertura florestal original. A Europa Ocidental perdeu 99,7% de suas florestas primárias; a Ásia, 94%; a África, 92%; a Oceania, 78%; a América do Norte, 66%; e a América do Sul, 54%. Cerca de 45% das florestas tropicais, que cobriam originalmente 14 milhões de km², desapareceram nas últimas décadas. No caso da Amazônia Brasileira, o desmatamento da região, que até 1970 era de apenas 1%, saltou para quase 15% em 1999. Uma área do tamanho da França desmatada em apenas 30 anos.
Paulo Adário, Coordenador da Campanha da Amazônia do Greenpeace.

TEXTO 4:
De uma coisa temos certeza: a terra não pertence ao homem branco; o homem branco é que pertence à terra. Disso temos certeza. Todas as coisas estão relacionadas como o sangue que une uma família. Tudo está associado. O que fere a terra, fere também os filhos da terra. O homem não tece a teia da vida; é antes um de seus fios. O que quer que faça a essa teia, faz a si próprio.
Trecho de carta atribuída ao chefe Seattle, da tribo Suquamish, 1854.""",

    "2002-regular": """Considerando a foto e os textos apresentados, redija um texto dissertativo-argumentativo sobre o tema "O direito de votar: como fazer dessa conquista um meio para promover as transformações sociais de que o Brasil necessita?"

TEXTO 2:
Para que existam hoje os direitos políticos, o direito de votar e ser votado, de escolher seus governantes e representantes, a sociedade lutou muito.
www.iarabernardi.gov.br, 01/03/02.

TEXTO 3:
A política foi inventada pelos humanos como o modo pelo qual pudessem expressar suas diferenças e conflitos sem transformá-los em guerra total, em uso da força e extermínio recíproco. A política foi inventada como o modo pelo qual a sociedade, internamente dividida, discute, delibera e decide em comum para aprovar ou reiterar ações que dizem respeito a todos os seus membros.
Marilena Chauí. Convite à filosofia. São Paulo: Ática, 1994.

TEXTO 4:
A democracia é subversiva. É subversiva no sentido mais radical da palavra. Em relação à perspectiva política, a razão da preferência pela democracia reside no fato de ser ela o principal remédio contra o abuso do poder. Uma das formas (não a única) é o controle pelo voto popular que o método democrático permite pôr em prática. Vox populi vox dei.
Norberto Bobbio. Qual socialismo? Discussão de uma alternativa. Rio de Janeiro: Paz e Terra, 1983.

TEXTO 5:
Se você tem mais de 18 anos, vai ter de votar nas próximas eleições. Se você tem 16 ou 17 anos, pode votar ou não. O mundo exige dos jovens que se arrisquem. Que alucinem. Que se metam onde não são chamados. Que sejam encrenqueiros e barulhentos. Que, enfim, exijam o impossível. Resta construir o mundo do amanhã. Parte desse trabalho é votar. Não só cumprir uma obrigação. Tem de votar com hormônios, com ambição, com sangue fervendo nas veias.
André Forastieri. Muito além do voto. Época. 6 de maio de 2002.""",

    "2003-regular": """Considerando a leitura do quadro e dos textos, redija um texto dissertativo-argumentativo sobre o tema: "A violência na sociedade brasileira: como mudar as regras desse jogo?"

TEXTO 2:
Entender a violência, entre outras coisas, como fruto de nossa horrenda desigualdade social, não nos leva a desculpar os criminosos, mas poderia ajudar a decidir que tipo de investimentos o Estado deve fazer para enfrentar o problema: incrementar violência por meio da repressão ou tomar medidas para sanear alguns problemas sociais gravíssimos?
Maria Rita Kehl. Folha de S. Paulo.

TEXTO 3:
Ao expor as pessoas a constantes ataques à sua integridade física e moral, a violência começa a gerar expectativas, a fornecer padrões de respostas. Episódios truculentos e situações-limite passam a ser imaginados e repetidos com o fim de legitimar a ideia de que só a força resolve conflitos. A violência torna-se um item obrigatório na visão de mundo que nos é transmitida.
Jurandir Costa. O medo social (adaptado).""",

    "2004-regular": """Com base nas ideias presentes nos textos, redija uma dissertação em prosa sobre o seguinte tema: "Como garantir a liberdade de informação e evitar abusos nos meios de comunicação?"

TEXTO 2:
Os programas sensacionalistas do rádio e os programas policiais de final da tarde em televisão saciam curiosidades perversas e até mórbidas tirando sua matéria-prima do drama de cidadãos humildes que aparecem nas delegacias como suspeitos de pequenos crimes. Ali, são entrevistados por intimidação. As câmeras invadem barracos e cortiços, e gravam sem pedir licença a estupefação de famílias de baixíssima renda.
Eugênio Bucci. Sobre ética e imprensa. São Paulo: Companhia das Letras, 2000.

TEXTO 3:
Quem fiscaliza [a imprensa]? Trata-se de tema complexo porque remete para a questão da responsabilidade não só das empresas de comunicação como também dos jornalistas. Alguns países, como a Suécia e a Grã-Bretanha, vêm há anos tentando resolver o problema da responsabilidade do jornalismo por meio de mecanismos que incentivam a auto-regulação da mídia.
http://www.eticanatv.org.br

TEXTO 4:
No Brasil, entre outras organizações, existe o Observatório da Imprensa – entidade civil, não-governamental e não partidária –, que pretende acompanhar o desempenho da mídia brasileira. "Os meios de comunicação de massa são majoritariamente produzidos por empresas privadas cujas decisões atendem legitimamente aos desígnios de seus acionistas ou representantes. Mas o produto jornalístico é, inquestionavelmente, um serviço público, com garantias e privilégios específicos previstos na Constituição Federal."
http://www.observatorio.ultimosegundo.ig.com.br (adaptado)""",

    "2005-regular": """Com base nas ideias presentes nos textos, redija uma dissertação sobre o tema: "O trabalho infantil na realidade brasileira."

TEXTO 2:
"A crueldade do trabalho infantil é um pecado social grave em nosso País. A dignidade de milhões de crianças brasileiras está sendo roubada diante do desrespeito aos direitos humanos fundamentais que não lhes são reconhecidos: por culpa do poder público, quando não atua de forma prioritária e efetiva, e por culpa da família e da sociedade, quando se omitem diante do problema ou quando simplesmente o ignoram em decorrência da postura individualista que caracteriza os regimes sociais e políticos do capitalismo contemporâneo, sem pátria e sem conteúdo ético."
Xisto T. de Medeiros Neto. A crueldade do trabalho infantil. Diário de Natal. 21/10/2000.

TEXTO 3:
"Submetidas aos constrangimentos da miséria e da falta de alternativas de integração social, as famílias optam por preservar a integridade moral dos filhos, incutindo-lhes valores, tais como a dignidade, a honestidade e a honra do trabalhador. Há um investimento no caráter moralizador e disciplinador do trabalho, como tentativa de evitar que os filhos se incorporem aos grupos de jovens marginais e delinquentes."
Joel B. Marin. O trabalho infantil na agricultura moderna.

TEXTO 4:
"Art. 4º – É dever da família, da comunidade, da sociedade em geral e do Poder Público assegurar, com absoluta prioridade, a efetivação dos direitos referentes à vida, à saúde, à alimentação, à educação, ao esporte, ao lazer, à profissionalização, à cultura, à dignidade, ao respeito, à liberdade e à convivência familiar e comunitária."
Estatuto da Criança e do Adolescente. Lei nº 8.069, de 13 de julho de 1990.""",

    "2006-regular": """Considerando que os textos têm caráter apenas motivador, redija um texto dissertativo a respeito do seguinte tema: "O poder de transformação da leitura."

TEXTO 1:
Uma vez que nos tornamos leitores da palavra, invariavelmente estaremos lendo o mundo sob a influência dela, tenhamos consciência disso ou não. A partir de então, mundo e palavra permearão constantemente nossa leitura e inevitáveis serão as correlações, de modo intertextual, simbiótico, entre realidade e ficção. Lemos porque a necessidade de desvendar caracteres, letreiros, números faz com que passemos a olhar, a questionar, a buscar decifrar o desconhecido.
Inajá Martins de Almeida. O ato de ler (com adaptações).

TEXTO 2:
Minha mãe muito cedo me introduziu aos livros. Embora nos faltassem móveis e roupas, livros não poderiam faltar. E estava absolutamente certa. Entrei na universidade e tornei-me escritor. Posso garantir: todo escritor é, antes de tudo, um leitor.
Moacyr Scliar. O poder das letras. In: TAM Magazine, jul./2006.

TEXTO 3:
Existem inúmeros universos coexistindo com o nosso, neste exato instante, e todos bem perto de nós. Eles são bidimensionais e, em geral, neles imperam o branco e o negro. Estes universos bidimensionais que nos rodeiam guardam surpresas incríveis e inimagináveis! Viajamos instantaneamente aos mais remotos pontos da Terra ou do Universo; ficamos sabendo os segredos mais ocultos de vidas humanas e da natureza; atravessamos eras num piscar de olhos. Estou falando dos universos a que chamamos de livros.
amigosdolivro.com.br (com adaptações).""",

    "2007-regular": """Todos reconhecem a riqueza da diversidade no planeta. Mil aromas, cores, sabores, texturas, sons encantam as pessoas no mundo todo; nem todas, entretanto, conseguem conviver com as diferenças individuais e culturais. Considerando a figura e os textos como motivadores, redija um texto dissertativo-argumentativo a respeito do seguinte tema: "O desafio de se conviver com a diferença."

TEXTO 2:
A cultura adquire formas diversas através do tempo e do espaço. Essa diversidade se manifesta na originalidade e na pluralidade de identidades que caracterizam os grupos e as sociedades que compõem a humanidade. Fonte de intercâmbios, de inovação e de criatividade, a diversidade cultural é, para o gênero humano, tão necessária como a diversidade biológica para a natureza. Nesse sentido, constitui o patrimônio comum da humanidade e deve ser reconhecida e consolidada em benefício das gerações presentes e futuras.
UNESCO. Declaração Universal sobre a Diversidade Cultural.""",

    "2008-regular": """O texto acima, que focaliza a relevância da região amazônica para o meio ambiente e para a economia brasileira, menciona a "máquina de chuva da Amazônia". Suponha que, para manter essa "máquina de chuva" funcionando, tenham sido sugeridas as ações a seguir:

1. Suspender completa e imediatamente o desmatamento na Amazônia, que permaneceria proibido até que fossem identificadas áreas onde se poderia explorar, de maneira sustentável, madeira de florestas nativas.

2. Efetuar pagamentos a proprietários de terras para que deixem de desmatar a floresta, utilizando-se recursos financeiros internacionais.

3. Aumentar a fiscalização e aplicar pesadas multas àqueles que promoverem desmatamentos não-autorizados.

Escolha uma dessas ações e, a seguir, redija um texto dissertativo, ressaltando as possibilidades e as limitações da ação escolhida.""",

    "2009-regular": """Com base na leitura dos textos motivadores seguintes e dos conhecimentos construídos ao longo de sua formação, redija um texto dissertativo-argumentativo em norma culta escrita da língua portuguesa sobre o tema "O indivíduo frente à ética nacional", apresentando proposta de ação social que respeite os direitos humanos. Não se esqueça: seu texto deve ter mais de 7 (sete) linhas e, no máximo, 30 linhas.""",

    "2010-regular": """Com base na leitura dos seguintes textos motivadores e nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo em norma culta escrita da língua portuguesa sobre o tema "O Trabalho na construção da dignidade Humana", apresentando experiência ou proposta de ação social, que respeite os direitos humanos. Não se esqueça: seu texto deve ter mais de 7 (sete) linhas e, no máximo, 30 linhas.""",

    "2011-regular": """Com base na leitura dos textos motivadores seguintes e nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo em norma padrão da língua portuguesa sobre o tema "Viver em rede no século XXI: os limites entre o público e o privado", apresentando proposta de conscientização social que respeite os direitos humanos.

TEXTO 1 - Liberdade sem fio:
A ONU acaba de declarar o acesso à rede um direito fundamental do ser humano – assim como saúde, moradia e educação. No mundo todo, pessoas começam a abrir seus sinais privados de wi-fi, organizações e governos se mobilizam para expandir a rede para espaços públicos e regiões onde ela ainda não chega, com acesso livre e gratuito.
ROSA, G.; SANTOS, P. Galileu. Nº 240, jul. 2011 (fragmento).

TEXTO 2 - A internet tem ouvidos e memória:
As redes sociais são ótimas para disseminar ideias, tornar alguém popular e também arruinar reputações. Um dos maiores desafios dos usuários de internet é saber ponderar o que se publica nela. Especialistas recomendam que não se deve publicar o que não se fala em público, pois a internet é um ambiente social e, ao contrário do que se pensa, a rede não acoberta anonimato, uma vez que mesmo quem se esconde atrás de um pseudônimo pode ser rastreado e identificado. Aqueles que, por impulso, se exaltam e cometem gafes podem pagar caro.
http://www.terra.com.br. Acesso em: 30 jun. 2011 (adaptado).""",

    "2012-regular": """A partir da leitura dos textos motivadores seguintes e com base nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo em norma padrão da língua portuguesa sobre o tema "O movimento imigratório para o Brasil no século XXI", apresentando proposta de intervenção, que respeite os direitos humanos.

TEXTO 1:
Ao desembarcar no Brasil, os imigrantes trouxeram muito mais do que o anseio de refazer suas vidas trabalhando nas lavouras de café e no início da indústria paulista. Nos séculos XIX e XX, os representantes de mais de 70 nacionalidades e etnias chegaram com o sonho de "fazer a América" e acabaram por contribuir expressivamente para a história do país e para a cultura brasileira. Deles, o Brasil herdou sobrenomes, sotaques, costumes, comidas e vestimentas.
http://www.museudaimigracao.org.br (adaptado).

TEXTO 3 - Trilha da Costura:
Os imigrantes bolivianos, pelo último censo, são mais de 3 milhões. A Bolívia ocupa a posição de 114º de acordo com os parâmetros estabelecidos pela ONU, sendo o país mais pobre da América do Sul, com 70% da população considerada miserável. Os principais países para onde os bolivianos imigrantes dirigem-se são: Argentina, Brasil, Espanha e Estados Unidos. Como a maioria da população tem baixa qualificação, os trabalhos artesanais, culturais, de campo e de costura são os de mais fácil acesso.
OLIVEIRA, R.T. http://www.ipea.gov.br (adaptado).""",

    "2013-regular": """A partir da leitura dos textos motivadores seguintes e com base nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo na modalidade escrita formal da língua portuguesa sobre o tema "Efeitos da implantação da Lei Seca no Brasil", apresentando proposta de intervenção, que respeite os direitos humanos.

TEXTO 1 - Qual o objetivo da "Lei Seca ao volante"?:
De acordo com a Associação Brasileira de Medicina de Tráfego (Abramet), a utilização de bebidas alcoólicas é responsável por 30% dos acidentes de trânsito. E metade das mortes, segundo o Ministério da Saúde, está relacionada ao uso do álcool por motoristas. Diante deste cenário preocupante, a Lei 11.705/2008 surgiu com uma enorme missão: alertar a sociedade para os perigos do álcool associado à direção. Para estancar a tendência de crescimento de mortes no trânsito, era necessária uma ação enérgica. E coube ao Governo Federal o primeiro passo. Mas para que todos ganhem, é indispensável a participação de estados, municípios e sociedade em geral.
www.dprf.gov.br. Acesso em: 20 jun. 2013.

TEXTO 3 - Repulsão magnética a beber e dirigir:
A lei da física que comprova que dois polos opostos se atraem em um campo magnético é um dos conceitos mais populares desse ramo do conhecimento. A ideia de uma agência de comunicação em Belo Horizonte foi bem simples. Ímãs foram inseridos em bolachas utilizadas para descansar os copos. Em cada lado, há uma opção para o cliente: dirigir ou chamar um táxi depois de beber. Ao tentar descansar seu copo com a opção dirigir, os ímãs causavam repulsão; se estivesse mostrando o lado com o desenho de um táxi, ela rapidamente grudava. A ideia surgiu da necessidade de passar a mensagem de uma forma leve e no exato momento do consumo.
www.operacaoleisecarj.rj.gov.br. Acesso em: 20 jun. 2013 (adaptado).""",

    "2014-regular": """A partir da leitura dos textos motivadores seguintes e com base nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo na modalidade escrita formal da língua portuguesa sobre o tema "Publicidade infantil em questão no Brasil", apresentando proposta de intervenção, que respeite os direitos humanos.""",

    "2015-regular": """A partir da leitura dos textos motivadores seguintes e com base nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo em modalidade escrita formal da língua portuguesa sobre o tema "A persistência da violência contra a mulher na sociedade brasileira", apresentando proposta de intervenção que respeite os direitos humanos.

TEXTO 1:
Nos 30 anos decorridos entre 1980 e 2010 foram assassinadas no país acima de 92 mil mulheres, 43,7 mil só na última década. O número de mortes nesse período passou de 1.353 para 4.465, que representa um aumento de 230%, mais que triplicando o quantitativo de mulheres vítimas de assassinato no país.
WALSELFISZ, J. J. Mapa da Violência 2012. Atualização: Homicídio de mulheres no Brasil. www.mapadaviolencia.org.br.""",

    "2016-regular": """A partir da leitura dos textos motivadores e com base nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo em modalidade escrita formal da língua portuguesa sobre o tema "Caminhos para combater a intolerância religiosa no Brasil", apresentando proposta de intervenção, que respeite os direitos humanos.

TEXTO 1:
Em consonância com a Constituição da República Federativa do Brasil e com toda a legislação que assegura a liberdade de crença religiosa às pessoas, além de proteção e respeito às manifestações religiosas, a laicidade do Estado deve ser buscada, afastando a possibilidade de interferência de correntes religiosas em matérias sociais, políticas, culturais etc.
www.mprj.mp.br (fragmento).

TEXTO 2:
O direito de criticar dogmas e encaminhamentos é assegurado como liberdade de expressão, mas atitudes agressivas, ofensas e tratamento diferenciado a alguém em função de crença ou de não ter religião são crimes inafiançáveis e imprescritíveis.
STECK, J. Intolerância religiosa é crime de ódio e fere a dignidade. Jornal do Senado (fragmento).

TEXTO 3 - CAPÍTULO I - Dos Crimes Contra o Sentimento Religioso:
Art. 208 - Escarnecer de alguém publicamente, por motivo de crença ou função religiosa; impedir ou perturbar cerimônia ou prática de culto religioso; vilipendiar publicamente ato ou objeto de culto religioso: Pena - detenção, de um mês a um ano, ou multa.
BRASIL. Código Penal. www.planalto.gov.br (fragmento).""",

    "2017-regular": """A partir da leitura dos textos motivadores seguintes e com base nos conhecimentos construídos ao longo de sua formação, redija um texto dissertativo-argumentativo em norma padrão da língua portuguesa sobre o tema "Desafios para a formação educacional de surdos no Brasil" apresentando proposta de intervenção que respeite os direitos humanos.

TEXTO 1 - CAPÍTULO IV - DO DIREITO À EDUCAÇÃO:
Art. 27. A educação constitui direito da pessoa com deficiência, assegurados sistema educacional inclusivo em todos os níveis e aprendizado ao longo de toda a vida. Parágrafo único. É dever do Estado, da família, da comunidade escolar e da sociedade assegurar educação de qualidade à pessoa com deficiência, colocando-a a salvo de toda forma de violência, negligência e discriminação.
Art. 28. Incumbe ao poder público assegurar: IV – oferta de educação bilíngue, em Libras como primeira língua e na modalidade escrita da língua portuguesa como segunda língua, em escolas e classes bilíngues e em escolas inclusivas; XII – oferta de ensino da Libras, do Sistema Braille e de uso de recursos de tecnologia assistiva, de forma a ampliar habilidades funcionais dos estudantes, promovendo sua autonomia e participação.
BRASIL. Lei nº 13.146, de 6 de julho de 2015.

TEXTO 3:
No Brasil, os surdos só começaram a ter acesso à educação durante o Império, no governo de Dom Pedro II, que criou a primeira escola de educação de meninos surdos, em 26 de setembro de 1857, na antiga capital do País, o Rio de Janeiro. Hoje, no lugar da escola funciona o Instituto Nacional de Educação de Surdos (Ines). Contudo, foi somente em 2002, por meio da sanção da Lei nº 10.436, que a Língua Brasileira de Sinais (Libras) foi reconhecida como meio legal de comunicação e expressão no País.
www.brasil.gov.br (adaptado).""",

    "2018-regular": """A partir da leitura dos textos motivadores e com base nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo em modalidade escrita formal da língua portuguesa sobre o tema "Manipulação do comportamento do usuário pelo controle de dados na internet", apresentando proposta de intervenção que respeite os direitos humanos.

TEXTO 1:
Às segundas-feiras pela manhã, os usuários de um serviço de música digital recebem uma lista personalizada de músicas que lhes permite descobrir novidades. Assim como os sistemas de outros aplicativos e redes sociais, este cérebro artificial consegue traçar um retrato automatizado do gosto de seus assinantes e constrói uma máquina de sugestões que não costuma falhar. O algoritmo constrói assim um universo cultural adequado e complacente com o gosto do consumidor, que pode avançar até chegar sempre a lugares reconhecíveis. Dessa forma, a filtragem de informação feita pelas redes sociais ou pelos sistemas de busca pode moldar nossa maneira de pensar. E esse é o problema principal, a ilusão de liberdade de escolha que muitas vezes é gerada pelos algoritmos.
VERDÚ, Daniel. O gosto na era do algoritmo. https://brasil.elpais.com/ (adaptado).

TEXTO 2:
Os algoritmos são literais. Em poucas palavras, são uma opinião embrulhada em código. E estamos caminhando para um estágio em que é a máquina que decide qual notícia deve ou não ser lida.
PEPE ESCOBAR. A silenciosa ditadura do algoritmo. https://outraspalavras.net/ (adaptado).

TEXTO 4:
Mudanças sutis nas informações às quais somos expostos podem transformar nosso comportamento. As redes têm selecionado as notícias sob títulos chamativos como "trending topics" ou critérios como "relevância". Mas nós praticamente não sabemos como isso tudo é filtrado. Quanto mais informações relevantes tivermos nas pontas dos dedos, melhor equipados estamos para tomar decisões. No entanto, surgem algumas tensões fundamentais: entre a conveniência e a deliberação; entre o que o usuário deseja e o que é melhor para ele; entre a transparência e o lado comercial. O que está em jogo não é tanto a questão "homem X máquina", mas sim a disputa "decisão informada X obediência influenciada".
CHATFIELD, Tom. Como a internet influencia secretamente nossas escolhas. https://www.bbc.com/ (adaptado).""",

    "2019-regular": """A partir da leitura dos textos motivadores e com base nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo em modalidade escrita formal da língua portuguesa sobre o tema "Democratização do acesso ao cinema no Brasil", apresentando proposta de intervenção que respeite os direitos humanos.

TEXTO 1:
No dia da primeira exibição pública de cinema — 28 de dezembro de 1895, em Paris —, um homem de teatro que trabalhava com mágicas, Georges Mélies, foi falar com Lumière, um dos inventores do cinema; queria adquirir um aparelho, e Lumière desencorajou-o, disse-lhe que o "Cinematógrapho" não tinha o menor futuro como espetáculo, era um instrumento científico para reproduzir o movimento e só poderia servir para pesquisas. Lumière enganou-se. Como essa estranha máquina de austeros cientistas virou uma máquina de contar estórias para enormes plateias?
BERNARDET, Jean-Claude. O que é Cinema. São Paulo: Brasiliense, 1993.

TEXTO 2:
Edgar Morin define o cinema como uma máquina que registra a existência e a restitui como tal, porém levando em consideração o indivíduo, ou seja, o cinema seria um meio de transpor para a tela o universo pessoal, solicitando a participação do espectador.
GUTFREIND, C. F. O filme e a representação do real. E-Compós, v. 6, 11, 2006 (adaptado).

TEXTO 4:
O Brasil já teve um parque exibidor vigoroso e descentralizado: quase 3.300 salas em 1975, uma para cada 30.000 habitantes, 80% em cidades do interior. Desde então, o país mudou. Quase 120 milhões de pessoas a mais passaram a viver nas cidades. A urbanização acelerada, a falta de investimentos em infraestrutura urbana, a baixa capitalização das empresas exibidoras, as mudanças tecnológicas alteraram a geografia do cinema. Em 1997, chegamos a pouco mais de 1.000 salas. Com a expansão dos shopping centers, a atividade de exibição se reorganizou. Foram privilegiadas as áreas de renda mais alta das grandes cidades. Populações inteiras foram excluídas do universo do cinema.
https://cinemapertodevoce.ancine.gov.br (fragmento).""",

    "2020-regular": """A partir da leitura dos textos motivadores e com base nos conhecimentos construídos ao longo de sua formação, redija um texto dissertativo-argumentativo em modalidade escrita formal da língua portuguesa sobre o tema "O Estigma associado às Doenças Mentais na sociedade brasileira", apresentando proposta de intervenção que respeite os direitos humanos.

TEXTO 1:
A maior parte das pessoas, quando houve falar em "saúde mental", pensa em "doença mental". Mas a saúde mental implica muito mais que a ausência de doenças mentais. Pessoas mentalmente saudáveis compreendem que ninguém é perfeito, que todos possuem limites e que não se pode ser tudo para todos. São capazes de enfrentar os desafios e as mudanças da vida cotidiana com equilíbrio e sabem procurar ajuda quando têm dificuldade em lidar com conflitos, perturbações, traumas ou transições importantes nos diferentes ciclos da vida.
https://www.saude.pr.gov.br/ (adaptado).

TEXTO 2:
A origem da palavra "estigma" aponta para marcas ou cicatrizes deixadas por feridas. Por extensão, em um período que remonta à Grécia Antiga, passou a designar também as marcas feitas com ferro em brasa em criminosos, escravos e outras pessoas que se desejava separar da sociedade "correta" e "honrada". Essa mesma palavra muitas vezes está presente no universo das doenças psiquiátricas. No lugar da marca de ferro, relegamos preconceito, falta de informação e tratamentos precários a pessoas que sofrem de depressão, ansiedade, transtorno bipolar e outros transtornos mentais graves. Achar que a manifestação de um transtorno mental é "frescura" está relacionado a um ideal de felicidade que não é igual para todo mundo.
https://www.abrata.org.br/ (adaptado).""",

    "2021-regular": """A partir da leitura dos textos motivadores e com base nos conhecimentos construídos ao longo de sua formação, redija um texto dissertativo-argumentativo em modalidade escrita formal da língua portuguesa sobre o tema "Invisibilidade e registro civil: garantia de acesso à cidadania no Brasil", apresentando proposta de intervenção que respeite os direitos humanos.

TEXTO 1:
Toda sexta-feira, o ônibus azul e branco estacionado no pátio da Vara da Infância e da Juventude, na Praça Onze, Centro do Rio, sacoleja com o entra e sai de gente a partir das 9h. Do lado de fora, nunca menos de 50 pessoas, todas pobres ou muito pobres, quase todas negras, cercam o veículo. Adultos, velhos e crianças estão ali para conseguir o que, no Brasil, é oficialmente reconhecido como o primeiro documento da vida - a certidão de nascimento. Ao longo do discurso desses entrevistados, fica clara a forma como os usuários se definem: "zero à esquerda", "cachorro", "um nada", "pessoa que não existe", entre outras, todas são expressões que conformam a ideia da pessoa sem registro de nascimento sobre si mesma como uma pessoa sem valor, cuja existência nunca foi oficialmente reconhecida pelo Estado.
ESCÓSSIA, F. M. Invisíveis: uma etnografia sobre identidade, direitos e cidadania. FGV. Rio de Janeiro. 2019.

TEXTO 3:
A certidão de nascimento é o primeiro e o mais importante documento do cidadão. Com ele, a pessoa existe oficialmente para o Estado e a sociedade. Só de posse da certidão é possível retirar outros documentos civis, como a carteira de trabalho, a carteira de identidade, o título de eleitor e o Cadastro de Pessoa Física (CPF). Além disso, para matricular uma criança na escola e ter acesso a benefícios sociais, a apresentação do documento é obrigatória.
https://www2.senado.leg.br/bdsf/handle/id/70224 (adaptado).""",

    "2022-regular": """A partir da leitura dos textos motivadores e com base nos conhecimentos construídos ao longo de sua formação, redija um texto dissertativo-argumentativo em modalidade escrita formal da língua portuguesa sobre o tema "Desafios para a valorização de comunidades e povos tradicionais no Brasil", apresentando proposta de intervenção que respeite os direitos humanos.

TEXTO 1:
Você sabe quais são as comunidades e os povos tradicionais brasileiros? Talvez indígenas e quilombolas sejam os primeiros que passam pela cabeça, mas, na verdade, além deles, existem 26 reconhecidos oficialmente. São pescadores artesanais, quebradeiras de coco babaçu, apanhadores de flores sempre-vivas, caatingueiros, extrativistas, para citar alguns, todos considerados culturalmente diferenciados, capazes de se reconhecerem entre si. Para uma pesquisadora da UnB, essas populações consideram a terra como uma mãe, e há uma relação de reciprocidade com a natureza.
https://g1.globo.com/economia/agronegocios/ (adaptado).

TEXTO 3:
O Ministério do Desenvolvimento Social (MDS) preside, desde 2007, a Comissão Nacional de Desenvolvimento Sustentável dos Povos e Comunidades Tradicionais (CNPCT), criada em 2006. Fruto dos trabalhos da CNPCT, foi instituída a Política Nacional de Desenvolvimento Sustentável dos Povos e Comunidades Tradicionais (PNPCT), criada em um contexto de busca de reconhecimento e preservação de outras formas de organização social por parte do Estado.
http://mds.gov.br (adaptado).

TEXTO 4 - Carta da Amazônia 2021:
Não podia ser mais estratégico para nós, Povos Indígenas, Populações e Comunidades Tradicionais brasileiras, reafirmarmos a defesa da sociobiodiversidade amazônica neste momento em que o mundo se volta a debater a crise climática da COP26. Nossos territórios protegidos e direitos respeitados são as reivindicações dos movimentos sociais e ambientais brasileiros. Propomos o que temos de melhor: a experiência das nossas sociedades e culturas históricas, construídas com base em nossos saberes tradicionais e ancestrais, além de nosso profundo conhecimento da natureza.
Entidades signatárias: CNS; Coiab; Conaq; MIQCB; Coica; ANA Amazônia e Confrem (adaptado).""",

    "2023-regular": """A partir da leitura dos textos motivadores e com base nos conhecimentos construídos ao longo de sua formação, redija um texto dissertativo-argumentativo em modalidade escrita formal da língua portuguesa sobre o tema "Desafios para o enfrentamento da invisibilidade do trabalho de cuidado realizado pela mulher no Brasil", apresentando proposta de intervenção que respeite os direitos humanos.

TEXTO 1 - O trabalho de cuidado não remunerado e mal pago e a crise global da desigualdade:
O trabalho de cuidado é essencial para nossas sociedades e para a economia. Ele inclui o trabalho de cuidar de crianças, idosos e pessoas com doenças e deficiências físicas e mentais, bem como o trabalho doméstico diário que inclui cozinhar, limpar, lavar, consertar coisas e buscar água e lenha. Se ninguém investisse tempo, esforços e recursos nessas tarefas diárias essenciais, comunidades, locais de trabalho e economias inteiras ficariam estagnados. Em todo o mundo, o trabalho de cuidado não remunerado e mal pago é desproporcionalmente assumido por mulheres e meninas em situação de pobreza. As mulheres são responsáveis por mais de três quartos do cuidado não remunerado e compõem dois terços da força de trabalho envolvida em atividades de cuidado remuneradas.
https://www.oxfam.org.br/ (adaptado).

TEXTO 3:
A sociedade brasileira tem passado por inúmeras transformações sociais ao longo das últimas décadas. Entre elas, as percepções sociais a respeito dos valores e das convenções de gênero e a forma como mulheres têm se inserido na sociedade. Algumas permanências, porém, chamam a atenção, como a delegação quase que exclusiva às famílias - e, nestas, às mulheres - de atividades relacionadas à reprodução da vida e da sociedade, usualmente nominadas trabalho de cuidado.
https://repositorio.ipea.gov.br/handle/11058/7412 (adaptado).""",

    "2024-regular": """Com base na leitura dos textos motivadores seguintes e nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo em norma padrão da língua portuguesa sobre o tema "Desafios para a valorização da herança africana no Brasil", apresentando proposta de ação social que respeite os direitos humanos.

TEXTO 1 - Herança:
O legado de crenças, conhecimentos, técnicas, costumes, tradições, transmitido por um grupo social de geração para geração; cultura.
HOUAISS, A.; VILLAR, M. S. Dicionário Houaiss da língua portuguesa. Rio de Janeiro: Objetiva, 2009 (adaptado).

TEXTO 2:
As culturas africanas e afro-brasileiras foram relegadas ao campo do folclore com o propósito de confiná-las ao gueto fossilizado da memória. Folclorizar, nesse caso, é reduzir uma cultura a um conjunto de representações estereotipadas, via de regra, alheias ao contexto que produziu essa cultura.
OLIVEIRA, E. D. A epistemologia da ancestralidade. Entrelugares, 2009.

TEXTO 4 - História afro-brasileira nas escolas:
As aulas sobre escravidão eram motivo de vergonha para uma professora quando ela estudava em uma escola municipal na zona sul de São Paulo. Naquela época, a história da população negra no Brasil era reduzida ao horror do período escravocrata. Não se falava na escola sobre temas como a história e a cultura afro-brasileira, muito menos sobre as grandes personalidades negras do país, como Luiz Gama e Carolina Maria de Jesus. A pedagoga, que é negra, tem orgulho de oferecer uma experiência diferente da que viveu em sala de aula para seus alunos. Agora os livros infantis levados para as turmas têm protagonistas pretos.
https://jornal.unesp.br/ (adaptado).

TEXTO 5 - Histórias para ninar gente grande (G.R.E.S. Mangueira, samba-enredo 2019):
Brasil, meu nego / Deixa eu te contar / A história que a história não conta / O avesso do mesmo lugar / Na luta é que a gente se encontra. Brasil, meu dengo / A Mangueira chegou / Com versos que o livro apagou / Desde 1500 tem mais invasão do que descobrimento / Tem sangue retinto pisado / Atrás do herói emoldurado / Mulheres, tamoios, mulatos / Eu quero um país que não está no retrato. Brasil, o teu nome é Dandara / E a tua cara é de cariri / Não veio do céu / Nem das mãos de Isabel / A liberdade é um dragão no mar de Aracati. Brasil, chegou a vez / De ouvir as Marias, Mahins, Marielles, malês.""",

    "2025-regular": """Com base na leitura dos textos motivadores seguintes e nos conhecimentos construídos ao longo de sua formação, redija texto dissertativo-argumentativo em norma padrão da língua portuguesa sobre o tema "Perspectivas acerca do envelhecimento na sociedade brasileira", apresentando proposta de ação social que respeite os direitos humanos.

TEXTO 1:
Em 2022, o total de pessoas com 65 anos de idade ou mais no país chegou a 10,9% da população — o equivalente a 57,4% a mais que em 2010, quando esse contingente era de 7,4% da população. O aumento da expectativa de vida e a diminuição da taxa de fecundidade no país são fatores que explicam esse fenômeno e o franco envelhecimento da população brasileira.
https://agenciadenoticias.ibge.gov.br/ (adaptado).

TEXTO 2:
Um movimento na internet, intitulado "Não somos velhos, somos experientes", protestou contra o uso do pictograma com bengala para os idosos e iniciou uma campanha para modificar esse símbolo. A imagem, anteriormente usada em placas e sinalizações, foi substituída por um novo desenho, com figura mais ativa, ao lado da inscrição "60+".
https://www12.senado.leg.br/ (adaptado).

TEXTO 3:
A velhice é tempo de se retratar consigo mesma, de falar da doença, da sexualidade, do tédio e da liberdade de não se encaixar mais nas expectativas sociais. "A velhice não é doença, é destino", escreve Rita Lee. A atriz Fernanda Montenegro, 95 anos, oferece em suas memórias uma síntese luminosa desse estágio: "A velhice é o tempo com dignidade. É o tempo em que a vida já foi vivida e, por isso mesmo, pode finalmente ser entendida sem medo, sem o pânico do ineditismo."
https://rascunho.com.br/ (adaptado).

TEXTO 5:
Dona Maria Rita era tão antiga que na casa da filha estavam habituados a ela como a um móvel velho. Ela não era novidade para ninguém. Mas nunca lhe passara pela cabeça ser móvel de ninguém. Era um lazer forçado que em certos momentos se tornava lancinante: nada tinha a fazer a não ser viver com o tempo, como um cachorro. Não fazia nada, fazia só isso: ser velha. Às vezes fazia questão de viver — achava que era necessário viver e agradecer a Deus.
LISPECTOR, C. Onde estivestes de noite. Rio de Janeiro: Francisco Alves, 1974.

TEXTO 6:
"São inúmeros os marcadores que definem quem vai viver e quem vai sucumbir diante de uma realidade imposta por um sistema bastante perverso", afirma o diretor do documentário "Quantos dias. Quantas noites". "O envelhecimento leva a maioria das pessoas a um declínio funcional. Mas, se você chega aos 75 tendo educação e saúde desiguais, principalmente pelo racismo, é muito difícil sobreviver com qualidade de vida", diz um médico gerontólogo.
https://revistagalileu.globo.com/ (adaptado).""",
}


def build_json():
    base = Path(__file__).parent / "enem_temas.json"
    dados = json.loads(base.read_text(encoding="utf-8"))

    atualizados = 0
    for item in dados:
        key = f"{item['ano']}-{item['edicao']}"
        if key in ENEM_TEXTS:
            item["texto"] = ENEM_TEXTS[key]
            atualizados += 1

    base.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    total = len(dados)
    print(f"Temas atualizados: {atualizados}/{total}")
    print(f"Temas sem texto: {total - atualizados}")
    for item in dados:
        if "texto" not in item:
            print(f"  - {item['ano']} [{item['edicao']}]: {item['titulo']}")


if __name__ == "__main__":
    build_json()
