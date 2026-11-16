import time

from .agents.claim_extractor import ClaimExtractor
from .agents.evidence_analyst import EvidenceAnalyst
from .agents.paper_finder import PaperFinder
from .agents.retraction_checker import RetractionChecker
from .agents.verification_agent import VerificationAgent

from .clients.crossref import CrossrefClient
from .clients.europepmc import EuropePmcClient
from .clients.openalex import OpenAlexClient
from .clients.pubmed import PubMedClient

from .config import settings


class Pipeline:

    def __init__(self, memory, llm, api_factory):
        self.memory = memory
        self.llm = llm
        self.api_factory = api_factory

    def _progress(self, inv, agent):

        def cb(done, total, msg=''):
            self.memory.update_agent(
                inv,
                agent,
                progress_done=done,
                progress_total=total,
                message=msg,
            )

        return cb

    @staticmethod
    def _outcome(result):
        """Normalise an agent return value into an outcome dict.

        Agents return ``{notes, errors, failed, data}``. Anything else is
        wrapped as a clean success so older-style returns keep working.
        """

        if (
            isinstance(result, dict)
            and 'data' in result
            and 'notes' in result
            and 'failed' in result
        ):
            return {
                'notes': list(result.get('notes') or []),
                'errors': int(result.get('errors') or 0),
                'failed': list(result.get('failed') or []),
                'data': result.get('data'),
                'message': result.get('message') or '',
            }

        return {
            'notes': [],
            'errors': 0,
            'failed': [],
            'data': result,
            'message': '',
        }

    def _stage(self, inv, agent, fn, retries=1):
        mem = self.memory

        mem.update_agent(
            inv,
            agent,
            status='running',
            message='Starting',
            started_at=time.time(),
        )

        for attempt in range(retries + 1):

            try:
                outcome = self._outcome(fn())

                problems = outcome['errors'] or len(outcome['failed'])
                status = (
                    'completed'
                    if problems == 0
                    else 'completed_with_errors'
                )

                message = outcome['message']

                if problems and not message:
                    message = (
                        'Finished, but %d item(s) could not be fully '
                        'checked.' % problems
                    )

                fields = {
                    'status': status,
                    'finished_at': time.time(),
                }

                # Only overwrite the progress message when we have one;
                # an empty message would erase the agent's own summary.
                if message:
                    fields['message'] = message

                mem.update_agent(inv, agent, **fields)

                return outcome

            except Exception as e:

                if attempt < retries and not isinstance(e, ValueError):

                    mem.update_agent(
                        inv,
                        agent,
                        status='retrying',
                        message='Retrying after error: ' + str(e),
                    )

                    time.sleep(2)
                    continue

                mem.update_agent(
                    inv,
                    agent,
                    status='failed',
                    message=str(e),
                    finished_at=time.time(),
                )

                raise

    def run(self, inv):
        m = self.memory
        m.set_status(inv, 'running')

        try:
            api = self.api_factory(inv)

            cr = CrossrefClient(api)
            oa = OpenAlexClient(api)
            epmc = EuropePmcClient(api)
            pmc = PubMedClient(api)

            checker = RetractionChecker(m, cr, epmc, pmc)

            p = lambda a: self._progress(inv, a)

            notes = []

            out = self._stage(
                inv,
                'claim_extractor',
                lambda: ClaimExtractor(m, self.llm).run(
                    inv,
                    p('claim_extractor'),
                ),
            )
            notes += out['notes']
            extraction_meta = out['data'] or {}

            out = self._stage(
                inv,
                'paper_finder',
                lambda: PaperFinder(m, cr, oa, epmc, pmc).run(
                    inv,
                    p('paper_finder'),
                ),
            )
            notes += out['notes']

            out = self._stage(
                inv,
                'retraction_checker',
                lambda: checker.run(
                    inv,
                    p('retraction_checker'),
                ),
            )
            notes += out['notes']

            out = self._stage(
                inv,
                'evidence_analyst',
                lambda: EvidenceAnalyst(m, self.llm).run(
                    inv,
                    p('evidence_analyst'),
                ),
            )
            notes += out['notes']

            ev = out['data'] or {}

            enabled = bool(getattr(self.llm, 'enabled', False))

            # The LLM object lives for the whole server, so its ``used``
            # counter accumulates across every investigation. Use the
            # evidence agent's own per-run tallies instead, otherwise a
            # report could claim more claims were read by the model than
            # this run actually contained.
            used = int(ev.get('llm', 0) or 0)
            lexical = int(ev.get('lexical', 0) or 0)
            skipped = int(ev.get('skipped', 0) or 0)
            full_text = int(ev.get('full_text', 0) or 0)

            last_error = getattr(self.llm, 'last_error', '') or ''

            if not enabled:
                notes.append(
                    'AI evidence analysis is off (no Gemini key), '
                    'so claim evidence cannot be fully verified; '
                    'keyword matching can only support WEAK SUPPORT.'
                )

            elif used == 0 and lexical:
                notes.append(
                    'AI evidence analysis was configured but every call '
                    'failed (%s), so all evidence used the keyword '
                    'fallback and nothing can be VERIFIED.'
                    % (last_error or 'unknown error')
                )

            context = {
                'extraction': extraction_meta,
                'ai': {
                    'enabled': enabled,
                    'used': used,
                    'lexical': lexical,
                    'skipped': skipped,
                    'full_text': full_text,
                    'full_text_mode': bool(
                        getattr(settings, 'full_text_mode', False)
                    ),
                    'model': getattr(self.llm, 'model', None),
                    'last_error': last_error or None,
                },
            }

            out = self._stage(
                inv,
                'verification_agent',
                lambda: VerificationAgent(m).run(
                    inv,
                    p('verification_agent'),
                    notes,
                    context,
                ),
            )

            report = out['data'] or {}

            # The uploaded document's own DOI (when its title page shows
            # one) is checked for retraction too, so a retracted paper is
            # flagged even if its reference list looks clean.
            document_doi = (extraction_meta or {}).get('document_doi')

            document = None

            if document_doi:
                document = {'doi': document_doi}

                try:
                    dr = checker.check_document(document_doi)

                    if dr is not None:
                        document['retraction'] = dr.model_dump()

                        if dr.status == 'retracted':
                            notes.append(
                                'The uploaded document itself has a '
                                'retraction notice on record (DOI %s).'
                                % document_doi
                            )

                except Exception as e:
                    document['error'] = str(e)

            report['document'] = document
            report['notes'] = notes

            agents = m.get_investigation(inv)['agents']
            report['agent_errors'] = sum(
                1
                for a in agents
                if a['status'] == 'completed_with_errors'
            )

            m.set_status(
                inv,
                'completed',
                report=report,
            )

        except Exception as e:
            m.set_status(
                inv,
                'failed',
                error=str(e),
            )
