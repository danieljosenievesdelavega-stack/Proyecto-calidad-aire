# Hallazgos y decisiones de calidad

## Duraciones de medicion

El archivo fuente contiene registros con duraciones distintas de 60 minutos,
incluidos periodos de varios dias. El ETL conserva esos registros, pero agrega
`es_horario`, que es verdadero cuando la diferencia entre `fecha_inicio` y
`fecha_final` esta entre 55 y 65 minutos. La EDA usa solo `es_horario` para
calcular coberturas, promedios temporales y relaciones meteorologicas.

El registro extremo de 393300 minutos no se elimina del historico: queda fuera
de los analisis horarios para evitar tratarlo como una observacion horaria.

## SO2

El archivo contiene picos de SO2 en Paipa de hasta 2204.6 ug/m3. El umbral
operativo superior del ETL es 3000 ug/m3 para no descartarlos automaticamente.
La clasificacion usa los percentiles observados: hasta p99 (59.86 ug/m3) se
marca como `valido`; por encima de p99 y hasta 3000 se marca como
`extremo_revisar`; por encima de 3000 se marca como `invalido` y se descarta.
Los registros `extremo_revisar` se conservan, pero quedan fuera de los analisis
descriptivos generales y alimentan la fase de deteccion de anomalias.

## Presion atmosferica

La variable `P` declara la unidad `mmHg` (`Milimetros de mercurio`). Su mediana
observada es aproximadamente 677 y el maximo aproximadamente 1027. En mmHg
esos valores son fisicamente incompatibles con la presion atmosferica terrestre;
en cambio, son consistentes con la escala de hectopascales (hPa). Esto sugiere
un error de etiquetado en los metadatos de la fuente. El ETL conserva el valor
original y usa el rango operacional 500-1050 sin convertirlo automaticamente;
la inconsistencia queda reportada como hallazgo de calidad de datos.

## Lectura del CSV

La lectura de DuckDB especifica UTF-8, delimitador coma y comillas dobles para
soportar campos textuales que contienen comas, como nombres de departamentos.