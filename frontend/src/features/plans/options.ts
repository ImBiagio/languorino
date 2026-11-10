import { gettext } from '../../lib/i18n'
import type { PrepMode } from '../../lib/types'

export const PREP_OPTIONS: { value: PrepMode; label: string; hint: string; icon: string }[] = [
  {
    value: 'none',
    label: gettext('Cucino al momento'),
    hint: gettext('Ogni pasto si prepara il giorno stesso'),
    icon: 'skillet',
  },
  {
    value: 'evening_before',
    label: gettext('La sera cucino anche per il pranzo dopo'),
    hint: gettext('La cena e la schiscetta di domani insieme'),
    icon: 'nights_stay',
  },
  {
    value: 'every_2',
    label: gettext('Cucino ogni 2 giorni'),
    hint: gettext('Una sessione per pranzi e cene di due giorni'),
    icon: 'counter_2',
  },
  {
    value: 'every_3',
    label: gettext('Cucino ogni 3 giorni'),
    hint: gettext('Meno sessioni, ricette che reggono in frigo'),
    icon: 'counter_3',
  },
  {
    value: 'weekend',
    label: gettext('Domenica e mercoledì'),
    hint: gettext('Due sessioni grandi per tutta la settimana'),
    icon: 'weekend',
  },
]

export const MINUTES_OPTIONS = [20, 30, 45, 60, 90, 120]
